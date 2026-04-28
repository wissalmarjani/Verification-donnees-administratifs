import json
from urllib import request, error


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1"


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(text[start : end + 1])


def extract_with_llm(text: str) -> dict:
    """
    Call local Ollama to extract structured fields as JSON.
    """

    prompt = (
        "Extract name, coordinates, and reference from this text and return JSON.\n"
        "Return ONLY valid JSON with keys: name, coordinates, reference.\n\n"
        f"Text:\n{text}"
    )
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")

    req = request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Ollama connection failed: {exc}") from exc

    response_text = body.get("response", "").strip()
    if not response_text:
        raise RuntimeError("Ollama returned an empty response")

    parsed = _extract_json_object(response_text)
    return {
        "name": str(parsed.get("name", "")).strip(),
        "coordinates": str(parsed.get("coordinates", "")).strip(),
        "reference": str(parsed.get("reference", "")).strip(),
    }
