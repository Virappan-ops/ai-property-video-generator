"""Tests for script_generator.py verifying exact facts and contact line omission."""

from pathlib import Path
from src.input_loader import PropertyData
from src.script_generator import generate_script_package


def test_script_contains_exact_supplied_facts() -> None:
    """Title, feature, closing, and narration texts contain exact supplied facts."""
    data = PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley, Sample City",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=["Spacious balcony", "Covered parking", "24/7 security"],
        contact_name="Sample Agent",
        contact_phone="+91 00000 00000",
        cta_text="Book your site visit today",
        images=[Path("img1.jpg")],
    )
    pkg = generate_script_package(data)
    assert "Sunrise Heights" in pkg.scenes[0].heading_lines[0]
    assert "2-BHK Apartment in Green Valley, Sample City" in pkg.scenes[0].heading_lines[1]
    assert pkg.scenes[0].body_line == "Price: ₹ 65,00,000"
    assert pkg.scenes[-1].body_line == "Sample Agent | +91 00000 00000"
    assert "Welcome to Sunrise Heights in Green Valley, Sample City." in pkg.narration_script
    assert "₹ 65,00,000" in pkg.narration_script


def test_contact_line_omitted_when_both_empty() -> None:
    """Closing scene body_line is empty when both contact_name and contact_phone are empty."""
    data = PropertyData(
        property_name="Lotus Residency",
        location="Sector 14",
        price="₹ 45,00,000",
        property_type="Plot",
        key_features=["Corner plot", "Park facing", "Wide road"],
        contact_name="",
        contact_phone="",
        cta_text="Call us today",
        images=[Path("img1.jpg")],
    )
    pkg = generate_script_package(data)
    assert pkg.scenes[-1].body_line == ""
    assert "For enquiries, contact" not in pkg.narration_script