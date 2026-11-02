"""Builds the video: zooming photos, sliding text, crossfades, per-scene voice-over and quiet music."""

import shutil
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from moviepy.audio.AudioClip import CompositeAudioClip  # type: ignore[import-untyped]
from moviepy.audio.fx.all import audio_fadeout, audio_loop, volumex  # type: ignore[import-untyped]
from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore[import-untyped]
from moviepy.video.VideoClip import ImageClip  # type: ignore[import-untyped]
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip  # type: ignore[import-untyped]
from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore[import-untyped]
from moviepy.video.fx.all import fadein, fadeout  # type: ignore[import-untyped]

import config
from src.errors import DependencyError, RenderError
from src.logger import log_step, log_warning
from src.overlay import create_text_overlay
from src.scene_planner import PlannedScene, ScenePlan
from src.zoom import create_zoom_clip


def verify_ffmpeg_available() -> None:
    """Confirm FFmpeg is available, either on PATH or through imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg  # type: ignore[import-untyped]

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return
    except Exception as exc:
        raise DependencyError(
            message="FFmpeg was not found. Install FFmpeg or run: pip install imageio-ffmpeg",
            suggestion="Run 'pip install imageio-ffmpeg==0.4.9' inside your virtual environment.",
        ) from exc

    raise DependencyError(
        message="FFmpeg was not found. Install FFmpeg or run: pip install imageio-ffmpeg",
        suggestion="Run 'pip install imageio-ffmpeg==0.4.9' inside your virtual environment.",
    )


def _text_slide(t: float) -> Any:
    """Text rises into place over SLIDE_UP_SECONDS with an ease-out curve, then holds still."""
    progress = min(max(t / config.SLIDE_UP_SECONDS, 0.0), 1.0)
    eased = 1.0 - (1.0 - progress) ** 3
    return ("center", int(round(config.SLIDE_UP_PIXELS * (1.0 - eased))))


def _scene_clip(scene: PlannedScene, temp_dir: Path) -> CompositeVideoClip:
    """One scene: zooming photo, text layer on top, then a fade in and out."""
    duration = scene.duration
    photo = create_zoom_clip(
        image_path=scene.image_path,
        duration=duration,
        scene_index=scene.scene_index,
        fps=config.FPS,
    )
    text_png = create_text_overlay(
        scene_text=scene.scene_text,
        scene_index=scene.scene_index,
        temp_dir=temp_dir,
    )
    text = ImageClip(str(text_png)).set_duration(duration).set_position(_text_slide)

    comp = CompositeVideoClip([photo, text], size=config.RESOLUTION).set_duration(duration)
    return comp.fx(fadein, config.CROSSFADE).fx(fadeout, config.CROSSFADE)


def _build_audio(
    plan: ScenePlan,
    music_path: Optional[Path],
    total: float,
    open_clips: List[AudioFileClip],
) -> Optional[CompositeAudioClip]:
    """Place each voice line at its scene start, and add quiet background music if available."""
    tracks: List[Any] = []

    for scene in plan.scenes:
        if scene.speech_path is not None and scene.speech_path.exists():
            clip = AudioFileClip(str(scene.speech_path))
            open_clips.append(clip)
            tracks.append(clip.set_start(scene.start + plan.crossfade))

    if music_path is not None:
        if music_path.exists() and music_path.is_file():
            try:
                raw = AudioFileClip(str(music_path))
                open_clips.append(raw)
                looped = audio_loop(raw, duration=total) if raw.duration < total else raw.subclip(0, total)
                quiet = volumex(looped, config.MUSIC_VOLUME)
                tracks.append(audio_fadeout(quiet, min(2.0, total)).set_start(0))
            except Exception as exc:  # noqa: BLE001
                log_warning(f"Warning: Could not load background music ({exc}). Continuing without music.")
        else:
            log_warning(f"Warning: Background music file '{music_path}' not found. Continuing without music.")

    if not tracks:
        return None
    return CompositeAudioClip(tracks).set_duration(total)


def build_and_export_video(
    plan: ScenePlan,
    output_path: Path,
    music_path: Optional[Path] = None,
    temp_dir: Path = Path(config.TEMP_DIR),
    keep_temp: bool = False,
) -> Path:
    """Build every scene, join them with crossfades, add audio, and write the 1280x720 MP4."""
    verify_ffmpeg_available()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    scene_clips: List[Any] = []
    open_audio_clips: List[AudioFileClip] = []
    final_video: Any = None

    try:
        total_scenes = len(plan.scenes)
        for scene in plan.scenes:
            log_step(f"Rendering scenes {scene.scene_index} of {total_scenes}...")
            scene_clips.append(_scene_clip(scene, temp_dir))

        padding_val: Any = -float(plan.crossfade)
        video = concatenate_videoclips(scene_clips, method="compose", padding=padding_val)
        total = float(video.duration)

        audio = _build_audio(plan, music_path, total, open_audio_clips)

        write_kwargs: Dict[str, Any] = {
            "fps": config.FPS,
            "codec": "libx264",
            "bitrate": config.BITRATE,
            "preset": config.ENCODE_PRESET,
            "threads": config.ENCODE_THREADS,
            "logger": None,
        }
        final_video = video
        if audio is not None:
            final_video = video.set_audio(audio)
            write_kwargs["audio_codec"] = "aac"
            write_kwargs["temp_audiofile"] = str(temp_dir / "temp_audio.m4a")
            write_kwargs["remove_temp"] = True
        else:
            write_kwargs["audio"] = False

        final_video.write_videofile(str(output_path), **write_kwargs)
        log_step(
            f"Exporting MP4... Saved to {output_path.as_posix()} "
            f"({int(round(total))} seconds, {config.RESOLUTION[0]}x{config.RESOLUTION[1]})"
        )
        return output_path

    except DependencyError:
        raise
    except Exception as exc:
        raise RenderError(
            message=f"Failed to render video to '{output_path}': {exc}",
            suggestion="Check available disk space and make sure the output file is not open in another player.",
        ) from exc
    finally:
        for ac in open_audio_clips:
            try:
                ac.close()
            except Exception:  # noqa: BLE001
                pass
        for sc in scene_clips:
            try:
                sc.close()
            except Exception:  # noqa: BLE001
                pass
        if final_video is not None:
            try:
                final_video.close()
            except Exception:  # noqa: BLE001
                pass

        if not keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)