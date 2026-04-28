import re


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def _normalize_coordinates(value: str) -> str:
    # Keep digits/sign/decimal/comma only for stable coordinate comparison.
    cleaned = re.sub(r"[^0-9,\.\-+ ]", "", (value or ""))
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def compare_data(pdf_data: dict, image_data: dict) -> dict:
    """
    Compare extracted structured data from PDF and image OCR outputs.
    """

    details = []
    status = "VALID"

    fields_to_compare = [
        ("name", _normalize_text),
        ("coordinates", _normalize_coordinates),
    ]

    for field, normalizer in fields_to_compare:
        pdf_value = (pdf_data or {}).get(field, "")
        image_value = (image_data or {}).get(field, "")

        normalized_pdf = normalizer(pdf_value)
        normalized_image = normalizer(image_value)

        if not normalized_pdf and not normalized_image:
            details.append(
                {
                    "field": field,
                    "result": "MISSING_BOTH",
                    "message": f"Field '{field}' is missing in both sources.",
                    "pdf_value": pdf_value,
                    "image_value": image_value,
                }
            )
            status = "ERROR"
            continue

        if normalized_pdf != normalized_image:
            details.append(
                {
                    "field": field,
                    "result": "MISMATCH",
                    "message": f"Mismatch on '{field}': PDF='{pdf_value}' vs IMAGE='{image_value}'.",
                    "pdf_value": pdf_value,
                    "image_value": image_value,
                }
            )
            status = "ERROR"
        else:
            details.append(
                {
                    "field": field,
                    "result": "MATCH",
                    "message": f"Field '{field}' matches.",
                    "pdf_value": pdf_value,
                    "image_value": image_value,
                }
            )

    return {"status": status, "details": details}
