from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from urllib.parse import urlsplit


DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:1.7b"
ALLOWED_ENDPOINT_PATHS = {"", "/", "/v1"}
LOCAL_ENV_KEYS = {"OLLAMA_ENDPOINT", "OLLAMA_MODEL"}


def load_local_config(env_file: str | Path | None = None) -> None:
    path = Path(env_file) if env_file else Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in LOCAL_ENV_KEYS or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ[key] = value


def ollama_model() -> str:
    model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
    if not model:
        raise ValueError("OLLAMA_MODEL no puede estar vacío.")
    return model


def ollama_base_url() -> str:
    endpoint = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_ENDPOINT).strip()
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port not in {None, 11434}
        or parsed.path.rstrip("/") not in ALLOWED_ENDPOINT_PATHS
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "OLLAMA_ENDPOINT debe apuntar únicamente a Ollama local en "
            "127.0.0.1:11434."
        )
    return DEFAULT_OLLAMA_ENDPOINT


def ollama_api_url() -> str:
    return f"{ollama_base_url()}/api/chat"


def ollama_openai_url() -> str:
    return f"{ollama_base_url()}/v1"


def validate_local_model(model: str | None = None) -> str:
    selected_model = model or ollama_model()
    if selected_model.casefold().endswith(":cloud"):
        raise ValueError("Los modelos Ollama en la nube están deshabilitados.")

    request = Request(f"{ollama_base_url()}/api/tags")
    opener = build_opener(ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    installed = {
        item.get("name") or item.get("model")
        for item in payload.get("models", [])
        if isinstance(item, dict)
    }
    if selected_model not in installed:
        raise ValueError(
            f"El modelo {selected_model!r} no está instalado localmente en Ollama."
        )
    return selected_model
