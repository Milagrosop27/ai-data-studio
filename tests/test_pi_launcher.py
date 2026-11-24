import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.backend.history import HistoryStore
from scripts.invoke_pi import (
    build_pi_command,
    build_pi_env,
    build_prompt,
    make_model_config,
    resolve_conversation_id,
)


class PiLauncherTests(unittest.TestCase):
    def test_model_config_is_loopback_ollama_only(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "OLLAMA_MODEL": "qwen3:1.7b",
                "OLLAMA_ENDPOINT": "http://localhost:11434/v1",
            },
        ), patch("scripts.invoke_pi.validate_local_model", return_value="qwen3:1.7b"):
            model, endpoint, provider = make_model_config(Path(temp_dir))
            config_text = (Path(temp_dir) / "models.json").read_text(encoding="utf-8")
            config = json.loads(config_text)

            self.assertEqual(model, "qwen3:1.7b")
            self.assertEqual(endpoint, "http://127.0.0.1:11434/v1")
            self.assertEqual(provider, "ollama")
            self.assertEqual(config["providers"][provider]["apiKey"], "ollama")
            self.assertNotIn("gemini", config_text.lower())

    def test_remote_ollama_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "OLLAMA_MODEL": "qwen3:1.7b",
                "OLLAMA_ENDPOINT": "https://remote.example/v1",
            },
        ), patch("scripts.invoke_pi.validate_local_model", return_value="qwen3:1.7b"):
            with self.assertRaisesRegex(ValueError, "únicamente"):
                make_model_config(Path(temp_dir))

    def test_pi_process_does_not_inherit_api_keys_or_proxy_settings(self):
        env = build_pi_env(
            Path("C:/agent/pi"),
            {
                "PATH": "safe-path",
                "GOOGLE_API_KEY": "secret",
                "OPENAI_API_KEY": "secret",
                "HTTPS_PROXY": "http://proxy.example",
                "OLLAMA_ENDPOINT": "http://127.0.0.1:11434",
            },
        )

        self.assertEqual(env["PATH"], "safe-path")
        self.assertNotIn("GOOGLE_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertEqual(env["OLLAMA_ENDPOINT"], "http://127.0.0.1:11434")
        self.assertEqual(env["PI_CODING_AGENT_DIR"], str(Path("C:/agent/pi")))

    def test_pi_prompt_uses_prior_events_without_repeating_the_new_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history = HistoryStore(
                Path(temp_dir) / "history.sqlite3",
                key_path=Path(temp_dir) / "history-key.dpapi",
            )
            history.record_event(
                conversation_id="conversation",
                event_type="user_request",
                content="Petición anterior",
                harness="pi",
                model="test",
                status="ok",
            )
            history.record_event(
                conversation_id="conversation",
                event_type="agent_response",
                content="Respuesta anterior",
                harness="pi",
                model="test",
                status="ok",
            )

            prompt = build_prompt(history, "conversation", "Petición actual")

        self.assertIn("Petición anterior", prompt)
        self.assertIn("Respuesta anterior", prompt)
        self.assertIn("Responde a la petición actual", prompt)
        self.assertTrue(prompt.endswith("Petición actual"))

    def test_new_requests_are_isolated_unless_continuation_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history = HistoryStore(
                Path(temp_dir) / "history.sqlite3",
                key_path=Path(temp_dir) / "history-key.dpapi",
            )
            history.record_event(
                conversation_id="previous-conversation",
                event_type="user_request",
                content="Contexto anterior",
                harness="pi",
                model="test",
                status="ok",
            )

            fresh_id = resolve_conversation_id(history, continue_conversation=False)
            continued_id = resolve_conversation_id(history, continue_conversation=True)

        self.assertNotEqual(fresh_id, "previous-conversation")
        self.assertEqual(continued_id, "previous-conversation")

    def test_ollama_command_enables_limited_file_tools_without_terminal_access(self):
        command = build_pi_command(
            "pi.cmd",
            "ollama",
            "qwen3:1.7b",
            "Read README.md",
        )

        self.assertIn("--tools", command)
        tools_index = command.index("--tools")
        self.assertEqual(command[tools_index + 1], "read,edit,write")
        self.assertNotIn("--no-tools", command)
        self.assertNotIn("powershell", command)
        self.assertNotIn("bash", command)
        self.assertIn("--append-system-prompt", command)
        self.assertIn(".env", command[command.index("--append-system-prompt") + 1])


if __name__ == "__main__":
    unittest.main()
