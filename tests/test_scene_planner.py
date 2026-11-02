"""Tests for scene_planner.py covering 0, 1, 3, and 5 features, image reuse, and duration bounds."""

from pathlib import Path
import pytest
import config
from src.input_loader import PropertyData
from src.scene_planner import plan_scenes


@pytest.mark.parametrize("feature_count", [0, 1, 3, 5])
def test_total_duration_within_20_to_40_seconds(feature_count: int) -> None:
    """Total video duration after crossfades stays between 20 and 40 seconds for 0, 1, 3, and 5 features."""
    features = [f"Feature {i}" for i in range(1, feature_count + 1)]
    images = [Path(f"img{i}.jpg") for i in range(1, 6)]
    data = PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=features,
        images=images,
    )
    plan = plan_scenes(data, prepared_images=images, narration_duration=18.0)
    assert config.MIN_TOTAL <= plan.total_duration <= config.MAX_TOTAL


def test_image_reuse_when_fewer_images_than_scenes() -> None:
    """When only 2 images exist for 5 scenes, images wrap around in order."""
    images = [Path("img1.jpg"), Path("img2.jpg")]
    data = PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=["F1", "F2", "F3"],
        images=images,
    )
    plan = plan_scenes(data, prepared_images=images)
    assert len(plan.scenes) == 5
    assert [s.image_path for s in plan.scenes] == [
        Path("img1.jpg"),
        Path("img2.jpg"),
        Path("img1.jpg"),
        Path("img2.jpg"),
        Path("img1.jpg"),
    ]


def test_long_narration_triggers_shortening_flag() -> None:
    """Narration longer than 40 seconds marks script_shortened_level and caps video at 40s."""
    images = [Path("img1.jpg"), Path("img2.jpg"), Path("img3.jpg"), Path("img4.jpg")]
    data = PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=["F1", "F2", "F3", "F4", "F5"],
        images=images,
    )
    plan = plan_scenes(data, prepared_images=images, narration_duration=45.0)
    assert plan.script_shortened_level == 1
    assert config.MIN_TOTAL <= plan.total_duration <= config.MAX_TOTAL