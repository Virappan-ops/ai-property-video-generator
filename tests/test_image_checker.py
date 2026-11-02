"""Tests for image_checker.py covering skipping missing images, zero usable images, and 1344x756 output."""

from pathlib import Path
from PIL import Image
import pytest
import config
from src.errors import ImageError
from src.image_checker import check_and_prepare_images


def _make_img(path: Path, fmt: str = "JPEG", size: tuple[int, int] = (1600, 1000)) -> Path:
    img = Image.new("RGB", size, color=(60, 100, 140))
    img.save(path, format=fmt)
    return path


def test_jpg_and_png_accepted_and_sized_1344x756(tmp_path: Path) -> None:
    """JPG and PNG files are accepted and prepared at 1344x756."""
    img1 = _make_img(tmp_path / "a.jpg", "JPEG")
    img2 = _make_img(tmp_path / "b.png", "PNG")
    img3 = _make_img(tmp_path / "c.jpg", "JPEG")
    img4 = _make_img(tmp_path / "d.png", "PNG")

    out_dir = tmp_path / "temp"
    prepared, skipped = check_and_prepare_images([img1, img2, img3, img4], temp_dir=out_dir, base_dir=tmp_path)
    assert skipped == 0
    assert len(prepared) == 4
    with Image.open(prepared[0]) as im:
        assert im.size == config.PREPARED_SIZE


def test_missing_image_skipped_with_exact_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing image prints the required warning message and continues."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    valid = [_make_img(img_dir / f"img{i}.jpg") for i in range(1, 5)]
    missing = img_dir / "img9.jpg"

    prepared, skipped = check_and_prepare_images(
        valid + [missing], temp_dir=tmp_path / "temp", base_dir=tmp_path
    )
    assert skipped == 1
    assert len(prepared) == 4
    out = capsys.readouterr().out
    assert "Image 'images/img9.jpg' not found. Skipping it. 4 valid images remain." in out


def test_zero_valid_images_raises_image_error(tmp_path: Path) -> None:
    """Zero valid images raises ImageError with the mandatory message."""
    with pytest.raises(ImageError) as exc_info:
        check_and_prepare_images([tmp_path / "missing.jpg"], temp_dir=tmp_path / "temp", base_dir=tmp_path)
    assert exc_info.value.message == (
        "No usable images found. Add at least one image to the images folder or check the paths in property.json."
    )