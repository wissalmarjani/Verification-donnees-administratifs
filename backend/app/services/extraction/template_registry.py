DEFAULT_TEMPLATES = {
    "CC": {"consignee": [r"(?:consignee|notify)\s*[:\-]\s*(.+)"]},
    "INVOICE": {"gross_weight": [r"(?:gross\s+weight)\s*[:\-]\s*([0-9\., ]+)"]},
    "BC": {"destination": [r"(?:destination)\s*[:\-]\s*([A-Za-z0-9 ,\-]+)"]},
    "PHYTO": {"transport_type": [r"(?:transport\s+type)\s*[:\-]\s*(truck|container)"]},
}


def get_template(doc_type: str) -> dict:
    return DEFAULT_TEMPLATES.get(doc_type, {})
