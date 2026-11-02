"""Builds scene texts, captions, and narration scripts via template logic or optional AI."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple
import urllib.error
import urllib.request

import config
from src.fact_checker import check_facts
from src.input_loader import PropertyData
from src.logger import log_debug, log_warning


@dataclass
class SceneText:
    """Text content for an individual video scene."""

    scene_type: str  # "title", "feature", "overview", "cta"
    heading_lines: List[str]
    body_line: str = ""
    footer_text: str = ""
    image_label: str = ""  # Name of the photo shown in this scene ("" if unnamed)


@dataclass
class ScriptPackage:
    """Scene texts and the spoken narration script."""

    scenes: List[SceneText]
    narration_script: str
    narration_sentences: List[str]


def image_index_for_scene(position: int, scene_count: int, num_images: int) -> int:
    """Return the image index for a scene (Section 10.4).

    The title (position 0) uses the first image, the closing scene uses the last image,
    and the scenes in between take the next image in order, wrapping around if needed.
    """
    if num_images <= 0 or position <= 0:
        return 0
    if position >= scene_count - 1:
        return num_images - 1
    return position % num_images


def _base_scene_texts(data: PropertyData, max_features: int) -> List[SceneText]:
    """Generate the scene text layers required by Section 8.1 and Section 10.2."""
    scenes: List[SceneText] = []

    # 1. Title scene
    scenes.append(
        SceneText(
            scene_type="title",
            heading_lines=[
                data.property_name,
                f"{data.property_type} in {data.location}",
            ],
            body_line=f"Price: {data.price}",
            footer_text="",  # Footer appears on every scene except the title (Section 11.2)
        )
    )

    # 2. Feature and content scenes (Section 8.1 and 10.2)
    features = data.key_features[:max_features]
    if len(features) == 0:
        # 0 features: two 6.0-second overview scenes
        scenes.append(
            SceneText(
                scene_type="overview",
                heading_lines=[f"{data.property_type} at {data.location}"],
                body_line="",
                footer_text=data.property_name,
            )
        )
        scenes.append(
            SceneText(
                scene_type="overview",
                heading_lines=[f"Price: {data.price}"],
                body_line="",
                footer_text=data.property_name,
            )
        )
    else:
        for feat in features:
            scenes.append(
                SceneText(
                    scene_type="feature",
                    heading_lines=[feat],
                    body_line="",
                    footer_text=data.property_name,
                )
            )
        if len(features) < 3:
            # 1 or 2 features: one overview scene with the type, location and price
            scenes.append(
                SceneText(
                    scene_type="overview",
                    heading_lines=[f"{data.property_type} at {data.location}"],
                    body_line=f"Price: {data.price}",
                    footer_text=data.property_name,
                )
            )

    # 3. Closing enquiry scene
    contact_parts = [p for p in (data.contact_name, data.contact_phone) if p]
    scenes.append(
        SceneText(
            scene_type="cta",
            heading_lines=[data.cta_text],
            body_line=" | ".join(contact_parts),
            footer_text=data.property_name,
        )
    )

    return scenes


def build_scene_texts(data: PropertyData, max_features: int = config.MAX_FEATURES) -> List[SceneText]:
    """Build scene texts and attach the name of the photo used by each scene."""
    scenes = _base_scene_texts(data, max_features)
    num_images = len(data.images)
    labels = data.image_labels

    for pos, sc in enumerate(scenes):
        idx = image_index_for_scene(pos, len(scenes), num_images)
        sc.image_label = labels[idx] if idx < len(labels) else ""

    return scenes


def _format_feature_list(features: List[str]) -> str:
    """Format up to 6 features into natural English ('A, B, and C')."""
    items = features[: config.MAX_KEY_FEATURES_INPUT]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _spoken_scene_sentence(text: str, label: str) -> str:
    """Turn a scene heading into a spoken sentence, naming the photo when one exists."""
    clean = text.strip().rstrip(".")
    if label:
        return f"{clean}, as shown in the {label.lower()}."
    return f"{clean}."


def build_template_narration(data: PropertyData) -> Tuple[str, List[str]]:
    """Build the narration from the same scenes shown on screen, so voice-over and captions match.

    Returns (full_text, sentences).
    """
    sentences: List[str] = [
        f"Welcome to {data.property_name} in {data.location}.",
        f"This {data.property_type} is priced at {data.price}.",
    ]

    for sc in build_scene_texts(data):
        if sc.scene_type == "title":
            continue

        if sc.scene_type == "feature":
            sentences.append(_spoken_scene_sentence(sc.heading_lines[0], sc.image_label))

        elif sc.scene_type == "overview":
            heading = sc.heading_lines[0]
            if heading.startswith("Price:"):
                continue  # Price is already spoken in the introduction
            sentences.append(_spoken_scene_sentence(heading, sc.image_label))

        elif sc.scene_type == "cta":
            sentences.append(f"{data.cta_text.strip().rstrip('.')}.")
            if data.contact_name and data.contact_phone:
                sentences.append(f"For enquiries, contact {data.contact_name} at {data.contact_phone}.")
            elif data.contact_name:
                sentences.append(f"For enquiries, contact {data.contact_name}.")
            elif data.contact_phone:
                sentences.append(f"For enquiries, contact {data.contact_phone}.")

    return " ".join(sentences), sentences


def shorten_narration_script(data: PropertyData, drop_highlights: bool = False) -> str:
    """Shorten the narration script per Section 10.3 (drop contact sentence first, then highlights)."""
    s_intro = f"Welcome to {data.property_name} in {data.location}."
    s_price = f"This {data.property_type} is priced at {data.price}."
    cta_clean = f"{data.cta_text.rstrip('.')}."

    parts = [s_intro, s_price]
    if data.key_features and not drop_highlights:
        parts.append(f"Highlights include {_format_feature_list(data.key_features)}.")
    parts.append(cta_clean)
    return " ".join(parts)


def _try_ai_narration(data: PropertyData) -> Optional[str]:
    """Attempt optional AI narration using PROPERTY_AI_API_KEY; return None on any failure."""
    api_key = os.environ.get(config.AI_API_KEY_ENV, "").strip()
    if not api_key:
        log_warning(
            f"Note: Environment variable {config.AI_API_KEY_ENV} is not set. Falling back to template script."
        )
        return None

    facts_summary = (
        f"Property Name: {data.property_name}\n"
        f"Location: {data.location}\n"
        f"Property Type: {data.property_type}\n"
        f"Price: {data.price}\n"
        f"Key Features: {', '.join(data.key_features) if data.key_features else 'None'}\n"
        f"Photo Names: {', '.join(lbl for lbl in data.image_labels if lbl) or 'None'}\n"
        f"CTA: {data.cta_text}\n"
        f"Contact Name: {data.contact_name}\n"
        f"Contact Phone: {data.contact_phone}\n"
    )
    prompt = (
        "Write a friendly narration of 2 to 3 sentences for a real estate video using ONLY the facts below. "
        "Do not invent amenities, distances, prices, or claims. Spell the property name, location, and type "
        "exactly as given. Do not use superlatives like 'best', 'cheapest', or 'luxury'.\n\n"
        f"{facts_summary}"
    )
    log_debug(f"AI Prompt:\n{prompt}")

    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        ai_text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        log_debug(f"AI Response:\n{ai_text}")
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as exc:
        log_warning(f"Warning: AI narration request failed ({exc}). Falling back to template script.")
        return None

    passed, reasons = check_facts(ai_text, data)
    if not passed:
        log_warning(
            f"Warning: AI script failed fact check ({'; '.join(reasons)}). Falling back to template script."
        )
        return None

    return ai_text


def generate_script_package(data: PropertyData, use_ai: bool = False) -> ScriptPackage:
    """Produce scene texts and the validated narration script."""
    scenes = build_scene_texts(data)
    template_narration, sentences = build_template_narration(data)

    if use_ai:
        ai_script = _try_ai_narration(data)
        if ai_script:
            return ScriptPackage(scenes=scenes, narration_script=ai_script, narration_sentences=[ai_script])

    return ScriptPackage(
        scenes=scenes,
        narration_script=template_narration,
        narration_sentences=sentences,
    )


def save_script_file(script_pkg: ScriptPackage, output_video_path: Path) -> Path:
    """Save the narration script and scene texts next to the video."""
    out_dir = output_video_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = output_video_path.stem
    script_filename = "sample_script.txt" if stem == "sample_property_video" else f"{stem}_script.txt"

    script_path = out_dir / script_filename
    lines = [
        "=== NARRATION SCRIPT ===",
        script_pkg.narration_script,
        "",
        "=== SCENE CAPTIONS ===",
    ]
    for idx, sc in enumerate(script_pkg.scenes, start=1):
        lines.append(f"Scene {idx} ({sc.scene_type.upper()}):")
        for h in sc.heading_lines:
            lines.append(f"  Heading: {h}")
        if sc.body_line:
            lines.append(f"  Body:    {sc.body_line}")
        if sc.footer_text:
            lines.append(f"  Footer:  {sc.footer_text}")
        if sc.image_label:
            lines.append(f"  Photo:   {sc.image_label}")
        lines.append("")

    script_path.write_text("\n".join(lines), encoding="utf-8")
    return script_path