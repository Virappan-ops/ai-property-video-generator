"""Loads and validates property details from JSON or interactive CLI prompts."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Callable, List, Optional

import config
from src.errors import InputError
from src.logger import log_warning


@dataclass
class PropertyData:
    """Validated internal representation of property input data."""

    property_name: str
    location: str
    price: str
    property_type: str
    key_features: List[str] = field(default_factory=list)
    contact_name: str = ""
    contact_phone: str = ""
    cta_text: str = config.DEFAULT_CTA
    images: List[Path] = field(default_factory=list)
    narration_enabled: bool = config.NARRATION_DEFAULT
    music_path: Optional[Path] = None
    image_labels: List[str] = field(default_factory=list)  # Same order as images; "" means unnamed


REQUIRED_FIELDS = ("property_name", "location", "price", "property_type")


def _clean_label(value: Any) -> str:
    """Collapse whitespace and limit a photo name. Empty means unnamed."""
    text = " ".join(str(value or "").split())
    return text[: config.MAX_LABEL_LENGTH]


def validate_and_normalize(raw: dict[str, Any], base_dir: Path) -> PropertyData:
    """Validate dictionary fields according to Section 6.4 and return PropertyData."""
    for req in REQUIRED_FIELDS:
        if req not in raw or raw[req] is None:
            raise InputError(
                message=f"Missing required field '{req}' in property.json. Please add it and run again.",
                suggestion=f"Provide a non-empty string for '{req}' in your input.",
            )
        if not str(raw[req]).strip():
            raise InputError(
                message=f"Missing required field '{req}' in property.json. Please add it and run again.",
                suggestion=f"Ensure '{req}' is not empty or whitespace.",
            )

    property_name = str(raw["property_name"]).strip()
    location = str(raw["location"]).strip()
    price = str(raw["price"]).strip()
    property_type = str(raw["property_type"]).strip()

    raw_features = raw.get("key_features") or []
    if not isinstance(raw_features, list):
        raise InputError(
            message="Field 'key_features' must be a list of strings.",
            suggestion="Format 'key_features' as a JSON array of strings.",
        )

    cleaned_features = [str(f).strip() for f in raw_features if str(f).strip()]
    if len(cleaned_features) > config.MAX_KEY_FEATURES_INPUT:
        log_warning(
            f"Warning: {len(cleaned_features)} key_features supplied; using the first {config.MAX_KEY_FEATURES_INPUT}."
        )
        cleaned_features = cleaned_features[: config.MAX_KEY_FEATURES_INPUT]

    contact_name = str(raw.get("contact_name") or "").strip()
    contact_phone = str(raw.get("contact_phone") or "").strip()
    cta_raw = str(raw.get("cta_text") or "").strip()
    cta_text = cta_raw if cta_raw else config.DEFAULT_CTA

    narration_raw = raw.get("narration_enabled", config.NARRATION_DEFAULT)
    narration_enabled = bool(narration_raw) if narration_raw is not None else config.NARRATION_DEFAULT

    music_raw = str(raw.get("music_path") or "").strip()
    music_path: Optional[Path] = None
    if music_raw:
        m_candidate = Path(music_raw)
        music_path = m_candidate if m_candidate.is_absolute() else (base_dir / m_candidate)

    raw_images = raw.get("images")
    if not isinstance(raw_images, list) or len(raw_images) == 0:
        raise InputError(
            message="Missing required field 'images' in property.json. Please add it and run again.",
            suggestion="Provide a list of 4 to 8 relative image paths under 'images'.",
        )

    raw_labels = raw.get("image_labels") or []
    if not isinstance(raw_labels, list):
        raw_labels = []

    resolved_images: List[Path] = []
    resolved_labels: List[str] = []
    for i, img_entry in enumerate(raw_images):
        img_str = str(img_entry).strip()
        if not img_str:
            continue
        p = Path(img_str)
        resolved_images.append(p if p.is_absolute() else (base_dir / p))
        label_raw = raw_labels[i] if i < len(raw_labels) else ""
        resolved_labels.append(_clean_label(label_raw))

    if len(resolved_images) > config.MAX_IMAGES:
        log_warning(
            f"Warning: {len(resolved_images)} images supplied; using the first {config.MAX_IMAGES}."
        )
        resolved_images = resolved_images[: config.MAX_IMAGES]
        resolved_labels = resolved_labels[: config.MAX_IMAGES]

    return PropertyData(
        property_name=property_name,
        location=location,
        price=price,
        property_type=property_type,
        key_features=cleaned_features,
        contact_name=contact_name,
        contact_phone=contact_phone,
        cta_text=cta_text,
        images=resolved_images,
        narration_enabled=narration_enabled,
        music_path=music_path,
        image_labels=resolved_labels,
    )


def load_json_input(json_path: Path) -> PropertyData:
    """Load and validate a property JSON file."""
    if not json_path.exists() or not json_path.is_file():
        raise InputError(
            message=f"Input file '{json_path}' not found.",
            suggestion="Check the file path passed to --input.",
        )

    try:
        content = json_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InputError(
            message=f"Could not read {json_path.name}: line {exc.lineno}, column {exc.colno}",
            suggestion="Fix the JSON syntax error at the reported line and column.",
        ) from exc

    if not isinstance(data, dict):
        raise InputError(
            message=f"Could not read {json_path.name}: root element must be a JSON object.",
            suggestion="Wrap your property fields in curly braces { ... }.",
        )

    return validate_and_normalize(data, base_dir=json_path.parent)


def _ask_required(prompt_text: str, input_fn: Callable[[str], str]) -> str:
    """Prompt repeatedly until a non-empty string is provided."""
    while True:
        ans = input_fn(f"{prompt_text}: ").strip()
        if ans:
            return ans
        log_warning("This field is required. Please enter a value.")


def load_interactive_input(
    image_dir_override: Optional[Path] = None,
    input_fn: Callable[[str], str] = input,
) -> PropertyData:
    """Collect property details interactively in the 10-question sequence."""
    property_name = _ask_required("1. Property name (required)", input_fn)
    location = _ask_required("2. Location (required)", input_fn)
    price = _ask_required("3. Price (required)", input_fn)
    property_type = _ask_required("4. Property type (required)", input_fn)

    features_raw = input_fn("5. Key features, comma-separated (optional): ").strip()
    key_features = [f.strip() for f in features_raw.split(",") if f.strip()] if features_raw else []

    contact_name = input_fn("6. Contact name (optional): ").strip()
    contact_phone = input_fn("7. Contact phone (optional): ").strip()
    cta_text = input_fn(f"8. CTA text (optional, default '{config.DEFAULT_CTA}'): ").strip()

    narration_ans = input_fn("9. Narration on or off (optional, default on) [on/off]: ").strip().lower()
    narration_enabled = narration_ans not in ("off", "no", "false", "0")

    if image_dir_override is not None:
        img_folder = image_dir_override
    else:
        img_folder_str = _ask_required("10. Image folder path (required)", input_fn)
        img_folder = Path(img_folder_str)

    if not img_folder.exists() or not img_folder.is_dir():
        raise InputError(
            message=f"Image folder '{img_folder}' not found.",
            suggestion="Provide a valid directory containing 4 to 8 property photos.",
        )

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    found_images = sorted(
        [p for p in img_folder.iterdir() if p.is_file() and p.suffix.lower() in valid_exts]
    )
    if not found_images:
        raise InputError(
            message="No usable images found. Add at least one image to the images folder or check the paths in property.json.",
            suggestion="Place JPG, PNG, or WEBP photos in the specified folder.",
        )

    raw_dict = {
        "property_name": property_name,
        "location": location,
        "price": price,
        "property_type": property_type,
        "key_features": key_features,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "cta_text": cta_text or config.DEFAULT_CTA,
        "images": [str(p) for p in found_images],
        "narration_enabled": narration_enabled,
    }
    return validate_and_normalize(raw_dict, base_dir=Path("."))