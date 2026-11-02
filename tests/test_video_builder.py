"""End-to-end test for video_builder.py producing a 1280x720 MP4 in a temporary folder."""

from pathlib import Path
from PIL import Image
import pytest
from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore[import-untyped]
import config
from src.image_checker import check_and_prepare_images
from src.input_loader import PropertyData
from src.scene_planner import plan_scenes
from src.video_builder import build_and_export_video


@pytest.mark.slow
def test_video_builder_produces_valid_mp4(tmp_path: Path) -> None:
    """End-to-end render in silent mode produces a playable 1280x720 MP4 between 20 and 40 seconds."""
    img_paths = []
    for i in range(1, 5):
        p = tmp_path / f"img{i}.jpg"
        Image.new("RGB", (1600, 1000), color=(40 * i, 80, 120)).save(p)
        img_paths.append(p)

    data = PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley, Sample City",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=["Spacious balcony", "Covered parking", "24/7 security"],
        contact_name="Sample Agent",
        contact_phone="+91 00000 00000",
        cta_text="Book your site visit today",
        images=img_paths,
        narration_enabled=False,
    )

    temp_dir = tmp_path / "temp"
    prepared, _ = check_and_prepare_images(img_paths, temp_dir=temp_dir, base_dir=tmp_path)
    plan = plan_scenes(data, prepared_images=prepared, narration_duration=None)

    out_mp4 = tmp_path / "out" / "test_video.mp4"
    build_and_export_video(plan=plan, output_path=out_mp4, narration_path=None, temp_dir=temp_dir)

    assert out_mp4.exists()
    clip = VideoFileClip(str(out_mp4))
    try:
        assert list(clip.size) == list(config.RESOLUTION)
        assert config.MIN_TOTAL - 0.5 <= clip.duration <= config.MAX_TOTAL + 0.5
    finally:
        clip.close()