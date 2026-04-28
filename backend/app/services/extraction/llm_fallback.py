import json
from urllib import request, error

from app.core.config import settings


def extract_with_llm(raw_text: str) -> dict:
    if not settings.gemini_api_key:
        return {}
    prompt = (
        "Extract logistics fields from this document text and return JSON only.\n"
        "Required JSON keys:\n"
        "consignee, packages, gross_weight, commercial_weight, transport_unit_number,\n"
        "incoterm, destination, transport_type, exporter_name, importer_name,\n"
        "product_name, botanical_variety, net_weight.\n"
        "Use null when unknown. No markdown.\n\n"
        f"Document text:\n{raw_text[:20000]}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    try:
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
        data = json.loads(body)
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        if not text:
            return {}
        cleaned = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, ValueError):
        return {}
