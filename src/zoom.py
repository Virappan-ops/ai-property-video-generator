"""Implements smooth 24 fps Ken Burns slow zoom (1.00 to 1.06) alternating by scene index."""

from pathlib import Path
from typing import Tuple
import numpy as np
from PIL import Image
from moviepy.video.VideoClip import VideoClip  # type: ignore[import-untyped]
import config

LANCZOS_FILTER = getattr(Image, "LANCZOS", Image.Resampling.LANCZOS)


def compute_zoom_scale(
    t: float,
    duration: float,
    scene_index: int,
    zoom_start: float = config.ZOOM_START,
    zoom_end: float = config.ZOOM_END,
) -> float:
    """Compute zoom scale at time t (seconds).

    1-based scene_index: odd scenes (1, 3, 5...) zoom in (1.00 -> 1.06);
    even scenes (2, 4...) zoom out (1.06 -> 1.00).
    """
    if duration <= 0:
        progress = 0.0
    else:
        progress = max(0.0, min(1.0, t / float(duration)))

    if scene_index % 2 == 1:
        return zoom_start + (zoom_end - zoom_start) * progress
    return zoom_end - (zoom_end - zoom_start) * progress


def render_zoom_frame(
    base_img: Image.Image,
    scale: float,
    target_size: Tuple[int, int] = config.RESOLUTION,
) -> np.ndarray:
    """Crop a sub-rectangle from the 1344x756 prepared image and resize to 1280x720 RGB array."""
    out_w, out_h = target_size
    prep_w, prep_h = base_img.size

    crop_w = prep_w / float(scale)
    crop_h = prep_h / float(scale)

    left = (prep_w - crop_w) / 2.0
    top = (prep_h - crop_h) / 2.0
    right = left + crop_w
    bottom = top + crop_h

    zoomed = base_img.resize(
        (out_w, out_h),
        resample=LANCZOS_FILTER,
        box=(left, top, right, bottom),
    )
    return np.asarray(zoomed, dtype=np.uint8)


def create_zoom_clip(
    image_path: Path,
    duration: float,
    scene_index: int,
    fps: int = config.FPS,
) -> VideoClip:
    """Create a MoviePy VideoClip with continuous centered zoom at 24 fps."""
    base_img = Image.open(image_path).convert("RGB")
    if base_img.size != config.PREPARED_SIZE:
        base_img = base_img.resize(config.PREPARED_SIZE, LANCZOS_FILTER)

    def make_frame(t: float) -> np.ndarray:
        scale = compute_zoom_scale(t, duration, scene_index)
        return render_zoom_frame(base_img, scale, config.RESOLUTION)

    clip = VideoClip(make_frame, duration=duration)
    return clip.set_fps(fps)