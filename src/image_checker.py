"""Validates images and prepares 1344x756 cover-cropped copies for Ken Burns zoom."""

from pathlib import Path
from typing import List, Tuple
from PIL import Image, UnidentifiedImageError
import config
from src.errors import ImageError
from src.logger import log_warning

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
LANCZOS_FILTER = getattr(Image, "LANCZOS", Image.Resampling.LANCZOS)


def cover_resize_and_crop(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Resize and center-crop an image to fill target_size (width, height) without stretching."""
    target_w, target_h = target_size
    src_w, src_h = img.size

    if src_w == 0 or src_h == 0:
        raise ValueError("Image has zero width or height.")

    scale = max(target_w / float(src_w), target_h / float(src_h))
    new_w = max(target_w, int(round(src_w * scale)))
    new_h = max(target_h, int(round(src_h * scale)))

    resized = img.resize((new_w, new_h), LANCZOS_FILTER)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h

    return resized.crop((left, top, right, bottom))


def check_and_prepare_images(
    image_paths: List[Path],
    temp_dir: Path = Path(config.TEMP_DIR),
    base_dir: Path = Path("input"),
) -> Tuple[List[Path], int]:
    """Validate candidate images, save 1344x756 RGB copies in temp_dir, and return (prepared_paths, skipped_count)."""
    temp_dir.mkdir(parents=True, exist_ok=True)

    valid_inputs: List[Tuple[Path, Image.Image]] = []
    skipped = 0

    missing_or_bad: List[Tuple[str, str]] = []
    for raw_path in image_paths:
        display_path = _format_display_path(raw_path, base_dir)
        if not raw_path.exists() or not raw_path.is_file():
            missing_or_bad.append((display_path, "missing"))
            skipped += 1
            continue

        if raw_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            missing_or_bad.append((display_path, "unsupported"))
            skipped += 1
            continue

        try:
            with Image.open(raw_path) as im:
                im.verify()
            reopened = Image.open(raw_path).convert("RGB")
            valid_inputs.append((raw_path, reopened))
        except (UnidentifiedImageError, OSError, ValueError):
            missing_or_bad.append((display_path, "corrupt"))
            skipped += 1

    valid_count = len(valid_inputs)
    for display_path, reason in missing_or_bad:
        if reason == "missing":
            log_warning(
                f"Image '{display_path}' not found. Skipping it. {valid_count} valid images remain."
            )
        else:
            log_warning(
                f"Image '{display_path}' could not be opened ({reason}). Skipping it. {valid_count} valid images remain."
            )

    if valid_count == 0:
        raise ImageError(
            message="No usable images found. Add at least one image to the images folder or check the paths in property.json.",
            suggestion="Ensure at least one valid JPG, JPEG, PNG, or WEBP file exists at the configured path.",
        )

    if valid_count < config.MIN_IMAGES:
        log_warning(
            f"Warning: Only {valid_count} usable image(s) found (4 to 8 recommended). Images will be reused across scenes."
        )

    prepared_paths: List[Path] = []
    for idx, (orig_path, rgb_img) in enumerate(valid_inputs, start=1):
        try:
            prepared = cover_resize_and_crop(rgb_img, config.PREPARED_SIZE)
            out_path = temp_dir / f"prep_{idx:02d}_{orig_path.stem}.jpg"
            prepared.save(out_path, format="JPEG", quality=95)
            prepared_paths.append(out_path)
        finally:
            rgb_img.close()

    return prepared_paths, skipped


def _format_display_path(path: Path, base_dir: Path) -> str:
    """Return a clean relative POSIX path string for user-facing messages."""
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()