"""Writes the spoken line for each scene so the voice-over describes exactly what is on screen."""

import re
from typing import List

import config
from src.input_loader import PropertyData
from src.script_generator import SceneText


def apply_pronunciations(text: str) -> str:
    """Replace written words with the spoken form from config.PRONUNCIATIONS (case-insensitive)."""
    result = text
    # Longest keys first, so "Sunrise Heights" style phrases are matched before shorter words
    for word, spoken in sorted(config.PRONUNCIATIONS.items(), key=lambda kv: -len(kv[0])):
        pattern = r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])"
        result = re.sub(pattern, spoken, result, flags=re.IGNORECASE)
    return result


def _spoken(text: str) -> str:
    """Make text read naturally by a text-to-speech voice."""
    text = text.replace("₹", "Rupees ").replace("-BHK", " BHK")
    text = apply_pronunciations(text)
    return " ".join(text.split())


def scene_speech(scene: SceneText, data: PropertyData) -> str:
    """Return the spoken line for one scene. It describes only what this scene shows."""
    if scene.scene_type == "title":
        line = (
            f"Welcome to {data.property_name} in {data.location}. "
            f"This {data.property_type} is priced at {data.price}."
        )

    elif scene.scene_type == "feature":
        feature = scene.heading_lines[0].rstrip(".")
        if scene.image_label:
            line = f"{feature}, as seen in the {scene.image_label.lower()} image."
        else:
            line = f"{feature}."

    elif scene.scene_type == "overview":
        heading = scene.heading_lines[0].rstrip(".")
        if heading.startswith("Price:"):
            line = f"The price is {data.price}."
        else:
            line = f"{heading}."
            if scene.body_line:
                line += f" Priced at {data.price}."

    else:  # closing enquiry scene
        line = f"{data.cta_text.rstrip('.')}."
        if data.contact_name and data.contact_phone:
            line += f" For enquiries, contact {data.contact_name} at {data.contact_phone}."
        elif data.contact_name:
            line += f" For enquiries, contact {data.contact_name}."
        elif data.contact_phone:
            line += f" For enquiries, contact {data.contact_phone}."

    return _spoken(line)


def build_speech_lines(scenes: List[SceneText], data: PropertyData) -> List[str]:
    """Return one spoken line per scene, in scene order."""
    return [scene_speech(sc, data) for sc in scenes]