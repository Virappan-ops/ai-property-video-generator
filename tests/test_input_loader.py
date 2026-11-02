"""Tests for input_loader.py covering valid JSON, missing fields, malformed JSON, and truncation."""

import json
from pathlib import Path
import pytest
from src.errors import InputError
from src.input_loader import load_json_input


def test_valid_sample_json_loads(tmp_path: Path) -> None:
    """Valid JSON loads and narration defaults to True."""
    sample = {
        "property_name": "Sunrise Heights",
        "location": "Green Valley, Sample City",
        "price": "₹ 65,00,000",
        "property_type": "2-BHK Apartment",
        "key_features": ["Balcony", "Parking", "Security"],
        "images": ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"],
    }
    json_file = tmp_path / "property.json"
    json_file.write_text(json.dumps(sample), encoding="utf-8")

    data = load_json_input(json_file)
    assert data.property_name == "Sunrise Heights"
    assert data.price == "₹ 65,00,000"
    assert data.narration_enabled is True
    assert len(data.key_features) == 3


def test_missing_required_field_rejected(tmp_path: Path) -> None:
    """Missing location raises InputError with exact mandatory message."""
    sample = {
        "property_name": "Sunrise Heights",
        "location": "   ",
        "price": "₹ 65,00,000",
        "property_type": "2-BHK Apartment",
        "images": ["img1.jpg"],
    }
    json_file = tmp_path / "property.json"
    json_file.write_text(json.dumps(sample), encoding="utf-8")

    with pytest.raises(InputError) as exc_info:
        load_json_input(json_file)
    assert exc_info.value.message == (
        "Missing required field 'location' in property.json. Please add it and run again."
    )


def test_malformed_json_rejected(tmp_path: Path) -> None:
    """Malformed JSON raises InputError naming line and column."""
    json_file = tmp_path / "property.json"
    json_file.write_text('{"property_name": "Broken", ', encoding="utf-8")

    with pytest.raises(InputError) as exc_info:
        load_json_input(json_file)
    assert "Could not read property.json: line" in exc_info.value.message


def test_missing_input_file_rejected(tmp_path: Path) -> None:
    """Non-existent input file raises InputError."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(InputError) as exc_info:
        load_json_input(missing)
    assert f"Input file '{missing}' not found." in exc_info.value.message


def test_key_features_truncated_to_six(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """More than 6 key_features are truncated to 6 with a warning."""
    sample = {
        "property_name": "Sunrise Heights",
        "location": "Green Valley",
        "price": "₹ 65,00,000",
        "property_type": "Villa",
        "key_features": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"],
        "images": ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"],
    }
    json_file = tmp_path / "property.json"
    json_file.write_text(json.dumps(sample), encoding="utf-8")

    data = load_json_input(json_file)
    assert len(data.key_features) == 6
    captured = capsys.readouterr().out
    assert "using the first 6" in captured