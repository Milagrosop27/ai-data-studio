"""Run one auditable Pi request, keeping its transcript in the 48-hour SQLite store."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.history import HistoryStore
from app.backend.local_config import (
    load_local_config,
    ollama_model,
    ollama_openai_url,
    validate_local_model,
)
OLLAMA_SYSTEM_PROMPT = (
    "Trabaja únicamente con archivos pertinentes del workspace. No abras, muestres, "
    "edites ni reproduzcas secretos de .env o archivos privados de historial. "
    "No borres ni reemplaces datos existentes sin autorización explícita."
)


def load_project_env() -> None:
    load_local_config(ROOT / ".env")


def make_model_config(agent_dir: Path) -> tuple[str, str, str]:
    model = validate_local_model()
    endpoint = ollama_openai_url()
    pi_provider = "ollama"
    provider_config = {
        "baseUrl": endpoint,
        "api": "openai-completions",
        "models": [{"id": model, "name": model}],
        "apiKey": "ollama",
    }

    agent_dir.mkdir(parents=True, exist_ok=True)
    model_config = {
        "$schema": "https://pi.dev/schemas/models.schema.json",
        "providers": {pi_provider: provider_config},
    }
    (agent_dir / "models.json").write_text(
        json.dumps(model_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return model, endpoint, pi_provider


def build_prompt(history: HistoryStore, conversation_id: str, request: str) -> str:
    previous = history.conversation_events(conversation_id, harness="pi")
    context_events = previous[-12:]
    if not context_events:
        return request
    context = "\n".join(
        f"{'Usuario' if event.event_type == 'user_request' else 'Agente'}: {event.content}"
        for event in context_events
    )
    return (
        "El siguiente historial es solo contexto, no una petición nueva. "
        "Responde a la petición actual; ignora mensajes anteriores que no sean pertinentes.\n"
        "<historial_reciente>\n"
        f"{context}\n"
        "</historial_reciente>\n\n"
        f"Petición actual del usuario:\n{request}"
    )


def resolve_conversation_id(history: HistoryStore, continue_conversation: bool) -> str:
    if continue_conversation:
        return history.latest_conversation_id(harness="pi") or uuid.uuid4().hex
    return uuid.uuid4().hex


def build_pi_command(
    executable: str,
    pi_provider: str,
    model: str,
    prompt: str,
) -> list[str]:
    command = [
        executable,
        "--no-session",
        "--print",
        "--provider",
        pi_provider,
        "--model",
        model,
    ]
    command.extend(
        [
            "--tools",
            "read,edit,write",
            "--append-system-prompt",
            OLLAMA_SYSTEM_PROMPT,
        ]
    )
    command.append(prompt)
    return command


def build_pi_env(agent_dir: Path, source: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    for key in list(env):
        if key.upper().endswith("_API_KEY") or key.upper() in {
            "API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
        }:
            env.pop(key, None)
    env["PI_CODING_AGENT_DIR"] = str(agent_dir)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit a request to Pi and persist both sides for at most 48 hours."
    )
    parser.add_argument(
        "--continue",
        dest="continue_conversation",
        action="store_true",
        help="Continue the most recent Pi conversation using its recent history",
    )
    parser.add_argument("message", nargs="+", help="User request to send to Pi")
    args = parser.parse_args()
    request = " ".join(args.message)

    load_project_env()
    history = HistoryStore()
    model = ollama_model()
    conversation_id = resolve_conversation_id(history, args.continue_conversation)
    prompt = (
        build_prompt(history, conversation_id, request)
        if args.continue_conversation
        else request
    )
    history.record_event(
        conversation_id=conversation_id,
        event_type="user_request",
        content=request,
        harness="pi",
        model=model or "unconfigured",
        status="ok",
    )

    try:
        agent_dir = ROOT / ".agent_runtime" / "pi"
        model, _, pi_provider = make_model_config(agent_dir)
        pi_executable = shutil.which("pi.cmd" if os.name == "nt" else "pi")
        if not pi_executable:
            raise FileNotFoundError(
                "No se encontró el CLI de Pi; instálalo con "
                "'npm install -g --ignore-scripts @earendil-works/pi-coding-agent'."
            )
        env = build_pi_env(agent_dir)
        command = build_pi_command(
            pi_executable,
            pi_provider,
            model,
            prompt,
        )
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except (OSError, ValueError) as error:
        history.record_event(
            conversation_id=conversation_id,
            event_type="agent_response",
            content=str(error),
            harness="pi",
            model=model or "unconfigured",
            status="error",
        )
        print(f"Error de configuración/ejecución de Pi: {error}", file=sys.stderr)
        return 1

    response = result.stdout.strip()
    if result.returncode != 0:
        response = result.stderr.strip() or response or f"Pi terminó con código {result.returncode}."
    history.record_event(
        conversation_id=conversation_id,
        event_type="agent_response",
        content=response,
        harness="pi",
        model=model,
        status="ok" if result.returncode == 0 else "error",
    )
    output = result.stdout if result.returncode == 0 else (result.stderr or result.stdout)
    if output:
        print(
            output,
            end="" if output.endswith("\n") else "\n",
            file=sys.stdout if result.returncode == 0 else sys.stderr,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
