from __future__ import annotations

import json
import urllib.request

OLLAMA_BASE = "http://localhost:11434"


def list_models(base_url: str = OLLAMA_BASE) -> list[dict]:
    req = urllib.request.Request(f"{base_url}/api/tags")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return data.get("models", [])


def is_running(base_url: str = OLLAMA_BASE) -> bool:
    try:
        list_models(base_url)
        return True
    except Exception:
        return False
