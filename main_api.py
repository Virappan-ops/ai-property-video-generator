"""FastAPI backend: accepts property details and uploaded photos, returns a narrated MP4."""

import asyncio
import json
import re
import shutil
import traceback
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

import config
from src.errors import ImageError, InputError, PropertyVideoError
from src.image_checker import check_and_prepare_images
from src.input_loader import validate_and_normalize
from src.narrator import synthesize_scene_speech
from src.scene_planner import plan_scenes
from src.script_generator import build_scene_texts, generate_script_package, save_script_file
from src.speech import build_speech_lines
from src.video_builder import build_and_export_video

app = FastAPI(title="AI Property Video Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
JOB_ID_RE = re.compile(r"^[a-f0-9]{32}$")
OUTPUT_DIR = Path("output")


@app.get("/api/health")
def health() -> dict:
    """Simple check that the backend is running. Open http://127.0.0.1:8000/api/health to test."""
    return {"status": "ok"}


def _message(exc: PropertyVideoError) -> str:
    """Combine a custom error's message and suggestion into one API message."""
    return f"{exc.message} {exc.suggestion}".strip()


def _clean_label(value: object) -> str:
    """Collapse whitespace and cap the length of a photo name. Empty means unnamed."""
    text = " ".join(str(value or "").split())
    return text[: config.MAX_LABEL_LENGTH]


def _remove_job_dir(job_id: str) -> None:
    """Delete the temporary folder of a job."""
    shutil.rmtree(Path(config.TEMP_DIR) / job_id, ignore_errors=True)


def _verify_image(path: Path, original_name: str) -> None:
    """Raise HTTP 400 if Pillow cannot open the saved file as an image."""
    try:
        with Image.open(path) as im:
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"'{original_name}' is not a valid image. Upload a different file.",
        ) from exc


async def _save_uploads(
    images: List[UploadFile],
    names: list,
    upload_dir: Path,
) -> Tuple[List[str], List[str]]:
    """Save uploaded photos in order and return (saved_paths, labels)."""
    saved_paths: List[str] = []
    labels: List[str] = []

    for i, upload in enumerate(images, start=1):
        original = upload.filename or f"photo_{i}"
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXT:
            raise HTTPException(
                status_code=400,
                detail=f"'{original}' is not a JPG, PNG, or WEBP image.",
            )

        content = await upload.read()
        if len(content) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"'{original}' is larger than 15 MB. Please upload a smaller photo.",
            )

        dest = upload_dir / f"img{i}{suffix}"
        dest.write_bytes(content)
        _verify_image(dest, original)

        saved_paths.append(str(dest))
        name = names[i - 1] if i - 1 < len(names) else ""
        labels.append(_clean_label(name))

    return saved_paths, labels


def _resolve_music(music_path: Optional[Path]) -> Optional[Path]:
    """Use the music path from the request, or the default background track if it exists."""
    if music_path is not None:
        return music_path
    default = Path(config.DEFAULT_MUSIC_PATH)
    return default if default.exists() else None


def run_pipeline(raw: dict, job_id: str) -> str:
    """Run validation, photo prep, voice-over, scene plan and export for one job.

    Runs in a worker thread (see the endpoint). Returns the spoken script, one line per scene.
    """
    prop_data = validate_and_normalize(raw, base_dir=Path("."))

    temp_dir = Path(config.TEMP_DIR) / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    prepared_images, _ = check_and_prepare_images(prop_data.images, temp_dir=temp_dir)

    script_pkg = generate_script_package(prop_data, use_ai=False)
    base_scenes = build_scene_texts(prop_data, max_features=config.MAX_FEATURES)

    speech = None
    if prop_data.narration_enabled:
        lines = build_speech_lines(base_scenes, prop_data)
        speech = synthesize_scene_speech(lines, temp_dir)
        if speech is not None:
            script_pkg.narration_script = " ".join(lines)
        else:
            script_pkg.narration_script = "Voice-over unavailable (no internet connection). The video is silent."
    else:
        script_pkg.narration_script = "Silent video. No voice-over."

    output_path = OUTPUT_DIR / f"{job_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_script_file(script_pkg, output_path)

    plan = plan_scenes(prop_data, prepared_images, speech)

    build_and_export_video(
        plan=plan,
        output_path=output_path,
        music_path=_resolve_music(prop_data.music_path),
        temp_dir=temp_dir,
    )

    return script_pkg.narration_script


@app.post("/api/generate-video-upload")
async def generate_video_upload(
    property_json: str = Form(..., alias="property"),
    image_names: str = Form("[]"),
    images: List[UploadFile] = File(...),
) -> dict:
    """Generate a narrated property video from form details and uploaded photos."""
    try:
        payload = json.loads(property_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Property details are not valid JSON.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Property details must be a JSON object.")

    # Any extra field (such as an old output_format) is ignored by validate_and_normalize.

    try:
        names = json.loads(image_names)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Photo names are not valid JSON.")
    if not isinstance(names, list):
        names = []

    if not (config.MIN_IMAGES <= len(images) <= config.MAX_IMAGES):
        raise HTTPException(
            status_code=400,
            detail=f"Upload between {config.MIN_IMAGES} and {config.MAX_IMAGES} photos.",
        )

    job_id = uuid.uuid4().hex
    upload_dir = Path(config.TEMP_DIR) / job_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    try:
        saved_paths, labels = await _save_uploads(images, names, upload_dir)
        raw = {
            **payload,
            "images": saved_paths,
            "image_labels": labels,
        }
        script_text = await asyncio.to_thread(run_pipeline, raw, job_id)

    except HTTPException:
        _remove_job_dir(job_id)
        raise
    except (InputError, ImageError) as exc:
        _remove_job_dir(job_id)
        raise HTTPException(status_code=400, detail=_message(exc))
    except PropertyVideoError as exc:
        _remove_job_dir(job_id)
        raise HTTPException(status_code=500, detail=_message(exc))
    except Exception:
        traceback.print_exc()
        _remove_job_dir(job_id)
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while generating the video. Check the server terminal for details.",
        )

    _remove_job_dir(job_id)

    return {
        "success": True,
        "video_url": f"/api/videos/{job_id}",
        "script": script_text,
    }


@app.get("/api/videos/{job_id}")
def get_video(job_id: str) -> FileResponse:
    """Return a generated MP4 by its job id."""
    if not JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=404, detail="Video not found")

    video_file = OUTPUT_DIR / f"{job_id}.mp4"
    if not video_file.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        path=video_file,
        media_type="video/mp4",
        filename="property_video.mp4",
    )