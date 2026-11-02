"""Premium 1280x720 RGBA text overlays: soft gradient, bold headings, accent details."""

from pathlib import Path
from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw, ImageFont

import config
from src.logger import log_warning
from src.script_generator import SceneText

FontType = Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]

SCRIM_TOP = 0.45          # Gradient starts at 45% of the frame height
SCRIM_MAX_ALPHA = 190     # Darkness at the bottom edge (0-255)
TEXT_START_Y = 462        # Where the lower-third text block begins
MARGIN_X = 64
EYEBROWS: Dict[str, str] = {
    "feature": "HIGHLIGHT",
    "overview": "DETAILS",
    "cta": "ENQUIRE",
}
_FONT_WARNING_SHOWN = False


def load_font(size: int, bold: bool = False) -> FontType:
    """Load DejaVu Sans (bold when requested) at the given size, falling back with one warning."""
    global _FONT_WARNING_SHOWN
    candidates = [config.FONT_BOLD_PATH, config.FONT_PATH] if bold else [config.FONT_PATH]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue

    if not _FONT_WARNING_SHOWN:
        log_warning(f"Warning: Font '{config.FONT_PATH}' not found. Using Pillow default font.")
        _FONT_WARNING_SHOWN = True
    default_loader: Any = ImageFont.load_default
    try:
        return default_loader(size=size)
    except TypeError:
        return ImageFont.load_default()

def _render_bytes(text: str, font: FontType) -> bytes:
    """Render text to a small grayscale bitmap, used to compare glyphs."""
    img = Image.new("L", (80, 80), 0)
    ImageDraw.Draw(img).text((4, 4), text, font=font, fill=255)
    return img.tobytes()


def _has_glyph(font: FontType, ch: str) -> bool:
    """True if the font draws ch as a real character, not the empty box shown for missing glyphs."""
    return _render_bytes(ch, font) != _render_bytes("\uFFFF", font)


def _display_text(text: str, font: FontType) -> str:
    """Replace the rupee sign with 'Rs.' only when the font cannot draw it."""
    if "₹" in text and not _has_glyph(font, "₹"):
        return text.replace("₹", "Rs. ")
    return text


def _wrap_text_to_width(text: str, font: FontType, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wrap text into lines that fit within max_width pixels."""
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _truncate_line_with_ellipsis(line: str, font: FontType, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    """Shorten a line with '...' so it stays within max_width."""
    bbox = draw.textbbox((0, 0), line, font=font)
    if (bbox[2] - bbox[0]) <= max_width:
        return line

    trimmed = line
    while trimmed and (draw.textbbox((0, 0), trimmed + "...", font=font)[2] > max_width):
        trimmed = trimmed[:-1].rstrip()
    return (trimmed + "...") if trimmed else "..."


def _draw_scrim(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    """Draw a soft gradient that fades from transparent to dark toward the bottom edge."""
    top = int(height * SCRIM_TOP)
    span = max(height - top, 1)
    for y in range(top, height):
        t = (y - top) / span
        alpha = int(SCRIM_MAX_ALPHA * (t ** 1.5))
        draw.line([(0, y), (width, y)], fill=(8, 8, 10, alpha))


def _draw_photo_tag(draw: ImageDraw.ImageDraw, label: str) -> None:
    """Draw the photo's name as an accent-colored tag in the top-left corner."""
    font = load_font(26, bold=True)
    text = _truncate_line_with_ellipsis(label, font, 660, draw)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x, pad_y = 20, 12
    x0, y0 = 40, 40
    x1 = x0 + text_w + 2 * pad_x
    y1 = y0 + text_h + 2 * pad_y

    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=tuple(config.ACCENT_RGB) + (235,))
    draw.text((x0 + pad_x, y0 + pad_y - bbox[1]), text, font=font, fill=(255, 255, 255, 255))


def create_text_overlay(
    scene_text: SceneText,
    scene_index: int,
    temp_dir: Path = Path(config.TEMP_DIR),
) -> Path:
    """Render one scene's text layer as a 1280x720 transparent PNG."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    width, height = config.RESOLUTION
    max_w = width - 2 * MARGIN_X

    white = (255, 255, 255, 255)
    soft = (228, 226, 220, 255)
    accent = tuple(config.ACCENT_RGB) + (255,)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _draw_scrim(draw, width, height)

    is_title = scene_text.scene_type == "title"
    heading_font = load_font(58 if is_title else 54, bold=True)
    subline_font = load_font(38, bold=True)
    body_font = load_font(30)
    footer_font = load_font(22)
    eyebrow_font = load_font(20, bold=True)

    y = TEXT_START_Y

    # Small category label in the accent color (not on the title card)
    eyebrow = EYEBROWS.get(scene_text.scene_type, "")
    if eyebrow:
        draw.text((MARGIN_X, y), eyebrow, font=eyebrow_font, fill=accent)
        y += 30

    # Short accent bar that separates the label from the heading
    draw.rounded_rectangle([MARGIN_X, y, MARGIN_X + 56, y + 5], radius=3, fill=accent)
    y += 22

    # Headings
    wrapped: List[str] = []
    for raw_line in scene_text.heading_lines:
        fixed = _display_text(raw_line, heading_font)
        wrapped.extend(_wrap_text_to_width(fixed, heading_font, max_w, draw))
    if len(wrapped) > 2:
        merged = " ".join(wrapped[1:])
        wrapped = [wrapped[0], _truncate_line_with_ellipsis(merged, heading_font, max_w, draw)]

    for idx, h_line in enumerate(wrapped):
        font = subline_font if (is_title and idx == 1) else heading_font
        fitted = _truncate_line_with_ellipsis(h_line, font, max_w, draw)
        draw.text((MARGIN_X, y), fitted, font=font, fill=white)
        bbox = draw.textbbox((0, 0), fitted, font=font)
        y += max(int(bbox[3] - bbox[1]), 36) + 12

    # Body line (price, contact)
    if scene_text.body_line:
        body_text = _display_text(scene_text.body_line.strip(), body_font)
        body = _truncate_line_with_ellipsis(body_text, body_font, max_w, draw)
        draw.text((MARGIN_X, y + 2), body, font=body_font, fill=soft)

    # Footer with the property name on every scene except the title
    if not is_title and scene_text.footer_text:
        footer = _truncate_line_with_ellipsis(scene_text.footer_text, footer_font, max_w, draw)
        draw.text((MARGIN_X, height - 46), footer, font=footer_font, fill=soft)

    if scene_text.image_label:
        _draw_photo_tag(draw, scene_text.image_label)

    out_path = temp_dir / f"overlay_scene_{scene_index:02d}.png"
    overlay.save(out_path, format="PNG")
    return out_path