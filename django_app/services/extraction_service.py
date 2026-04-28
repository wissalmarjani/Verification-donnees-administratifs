import re
from typing import Callable

from services.llm_service import extract_with_llm


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_with_regex(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    if not match:
        return ""
    return _clean_value(match.group(1))


def _extract_name(text: str) -> str:
    # Supports labels like: "Name: John Doe" or "Nom: John Doe"
    return _extract_with_regex(r"(?:name|nom)\s*[:\-]\s*([A-Za-zÀ-ÿ' -]{2,120})", text)


def _extract_coordinates(text: str) -> str:
    # Supports labels like: "Coordinates: 48.8566, 2.3522"
    # and GPS-like patterns embedded in text.
    labeled = _extract_with_regex(
        r"(?:coordinates?|coordonn[eé]es?)\s*[:\-]\s*([0-9\.\-]+\s*,\s*[0-9\.\-]+)",
        text,
    )
    if labeled:
        return labeled
    # Fallback pattern: decimal pair
    return _extract_with_regex(r"\b([\-+]?\d{1,3}\.\d{3,}\s*,\s*[\-+]?\d{1,3}\.\d{3,})\b", text)


def _extract_reference(text: str) -> str:
    # Supports: "Reference: ABC-1234", "Ref N°: 2024/001", etc.
    return _extract_with_regex(
        r"(?:reference|ref(?:erence)?|r[eé]f(?:[ée]rence)?)\s*(?:n[°o]\s*)?[:\-]\s*([A-Za-z0-9\-/_.]+)",
        text,
    )


# Registry keeps extraction modular and makes LLM fallback integration easy later.
FIELD_EXTRACTORS: dict[str, Callable[[str], str]] = {
    "name": _extract_name,
    "coordinates": _extract_coordinates,
    "reference": _extract_reference,
}


def _extract_structured_data_with_regex(text: str) -> dict:
    return {field: extractor(text or "") for field, extractor in FIELD_EXTRACTORS.items()}


def extract_structured_data(text: str) -> dict:
    """
    Extract structured fields using LLM first, then fallback to regex.
    """
    source_text = text or ""
    try:
        llm_result = extract_with_llm(source_text)
        # If LLM returns at least one meaningful field, keep it.
        if any((llm_result.get(k) or "").strip() for k in ("name", "coordinates", "reference")):
            return llm_result
    except Exception:
        # LLM failure must not break pipeline.
        pass

    return _extract_structured_data_with_regex(source_text)
