import json
from pathlib import Path


def load_rules() -> list[dict]:
    path = Path(__file__).parent / "default_rules.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
