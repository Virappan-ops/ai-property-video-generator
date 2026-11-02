"""Tests for zoom.py covering scale progression, frame dimensions, and alternating direction."""

from pathlib import Path
from PIL import Image
import pytest
import config
from src.zoom import compute_zoom_scale, create_zoom_clip


def test_zoom_scale_progression_and_alternating_direction() -> None:
    """Odd scenes zoom 1.00 -> 1.06; even scenes zoom 1.06 -> 1.00."""
    # Scene 1 (odd): zooms in
    assert compute_zoom_scale(0.0, 4.0, scene_index=1) == pytest.approx(1.00)
    assert compute_zoom_scale(4.0, 4.0, scene_index=1) == pytest.approx(1.06)

    # Scene 2 (even): zooms out
    assert compute_zoom_scale(0.0, 4.0, scene_index=2) == pytest.approx(1.06)
    assert compute_zoom_scale(4.0, 4.0, scene_index=2) == pytest.approx(1.00)


def test_every_output_frame_is_1280x720(tmp_path: Path) -> None:
    """Rendered zoom clip produces 1280x720 RGB frames across the scene duration."""
    img_path = tmp_path / "prep.jpg"
    Image.new("RGB", config.PREPARED_SIZE, color=(80, 120, 160)).save(img_path)

    clip = create_zoom_clip(img_path, duration=2.0, scene_index=1)
    try:
        for t in (0.0, 1.0, 2.0):
            frame = clip.get_frame(t)
            assert frame.shape == (config.RESOLUTION[1], config.RESOLUTION[0], 3)
    finally:
        clip.close()