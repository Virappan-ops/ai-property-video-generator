"""Tests for fact_checker.py covering invented prices, blocked phrases, and valid text."""

from pathlib import Path
from src.fact_checker import check_facts
from src.input_loader import PropertyData


def _sample_data() -> PropertyData:
    return PropertyData(
        property_name="Sunrise Heights",
        location="Green Valley, Sample City",
        price="₹ 65,00,000",
        property_type="2-BHK Apartment",
        key_features=["Spacious balcony", "24/7 security"],
        contact_name="Sample Agent",
        contact_phone="+91 00000 00000",
        cta_text="Book your site visit today",
        images=[Path("img1.jpg")],
    )


def test_passes_valid_fact_based_script() -> None:
    """Text containing only supplied facts passes."""
    data = _sample_data()
    text = (
        "Welcome to Sunrise Heights in Green Valley, Sample City. "
        "This 2-BHK Apartment is priced at ₹ 65,00,000 with 24/7 security."
    )
    passed, reasons = check_facts(text, data)
    assert passed is True
    assert reasons == []


def test_rejects_invented_price_or_number() -> None:
    """Invented number not in input fails fact checking."""
    data = _sample_data()
    text = "Welcome to Sunrise Heights in Green Valley, Sample City priced at ₹ 50,00,000."
    passed, reasons = check_facts(text, data)
    assert passed is False
    assert any("50,00,000" in r for r in reasons)


def test_rejects_blocked_phrase_guaranteed_returns() -> None:
    """Blocked phrase 'guaranteed returns' fails fact checking."""
    data = _sample_data()
    text = "Sunrise Heights in Green Valley, Sample City offers guaranteed returns."
    passed, reasons = check_facts(text, data)
    assert passed is False
    assert any("guaranteed returns" in r for r in reasons)