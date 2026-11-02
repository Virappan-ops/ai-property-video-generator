"""Verifies that generated scripts use only supplied property facts and no blocked phrases."""

import re
from typing import List, Tuple
from src.input_loader import PropertyData

BLOCKED_PHRASES = (
    "guaranteed returns",
    "best in city",
    "best in the city",
    "cheapest",
    "lowest price",
    "investment guaranteed",
)


def check_facts(generated_text: str, data: PropertyData) -> Tuple[bool, List[str]]:
    """Validate generated text against supplied PropertyData. Returns (passed, reasons)."""
    reasons: List[str] = []
    text_stripped = (generated_text or "").strip()

    # Check 4: Non-empty and at most 600 characters
    if not text_stripped:
        reasons.append("Generated text is empty.")
        return False, reasons
    if len(text_stripped) > 600:
        reasons.append(f"Generated text exceeds 600 characters ({len(text_stripped)} chars).")

    # Assemble corpus of all supplied input text
    input_corpus = " ".join(
        [
            data.property_name,
            data.location,
            data.price,
            data.property_type,
            " ".join(data.key_features),
            data.contact_name,
            data.contact_phone,
            data.cta_text,
        ]
    )

    # Check 1: Every number in the generated text appears in the input
    input_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", input_corpus))
    input_digits_only = {re.sub(r"[^\d]", "", n) for n in input_numbers if re.sub(r"[^\d]", "", n)}

    gen_numbers = re.findall(r"\d+(?:[.,]\d+)*", text_stripped)
    for num in gen_numbers:
        normalized_num = re.sub(r"[^\d]", "", num)
        if num not in input_numbers and normalized_num not in input_digits_only:
            reasons.append(f"Invented number '{num}' does not appear in the supplied input.")

    # Check 2: Property name, location, and property type are spelled exactly as supplied when present
    for label, exact_val in (
        ("property_name", data.property_name),
        ("location", data.location),
        ("property_type", data.property_type),
    ):
        pattern = re.compile(re.escape(exact_val), re.IGNORECASE)
        matches = pattern.findall(text_stripped)
        for m in matches:
            if m != exact_val:
                reasons.append(
                    f"Field '{label}' spelled as '{m}' instead of exact '{exact_val}'."
                )

    # Check 3: No blocked phrases (and 'luxury' only if present in input)
    lower_text = text_stripped.lower()
    for phrase in BLOCKED_PHRASES:
        if phrase in lower_text:
            reasons.append(f"Contains blocked phrase: '{phrase}'.")

    if "luxury" in lower_text and "luxury" not in input_corpus.lower():
        reasons.append("Contains blocked word 'luxury' not present in input.")

    return len(reasons) == 0, reasons