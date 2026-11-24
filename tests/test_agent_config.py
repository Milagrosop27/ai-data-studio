import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.backend.agent import LocalCsvAnalyst
from app.backend.local_config import (
    load_local_config,
    ollama_api_url,
    ollama_openai_url,
    validate_local_model,
)


class LocalAgentConfigurationTests(unittest.TestCase):
    def test_only_loopback_ollama_endpoints_are_accepted(self):
        with patch.dict(
            os.environ,
            {"OLLAMA_ENDPOINT": "http://localhost:11434/v1"},
        ):
            self.assertEqual(
                ollama_api_url(),
                "http://127.0.0.1:11434/api/chat",
            )
            self.assertEqual(
                ollama_openai_url(),
                "http://127.0.0.1:11434/v1",
            )

        with patch.dict(
            os.environ,
            {"OLLAMA_ENDPOINT": "https://remote.example/v1"},
        ):
            with self.assertRaisesRegex(ValueError, "únicamente"):
                ollama_api_url()

    def test_cloud_model_tags_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "nube"):
            validate_local_model("qwen3:cloud")

    def test_agent_sends_data_only_to_local_ollama_without_code_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = Path(temp_dir)
            csv_path = upload_dir / "dataset.csv"
            csv_path.write_text("month;revenue\nJanuary;12\n", encoding="utf-8")
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(
                {"message": {"content": "La suma es 12."}}
            ).encode("utf-8")
            opener = MagicMock()
            opener.open.return_value = response

            with (
                patch("app.backend.agent.UPLOAD_DIR", upload_dir),
                patch("app.backend.agent.validate_local_model", return_value="test-local-model"),
                patch("app.backend.agent.build_opener", return_value=opener),
                patch.dict(os.environ, {"OLLAMA_ENDPOINT": "http://127.0.0.1:11434"}),
            ):
                agent = LocalCsvAnalyst(csv_path, model="test-local-model")
                result = agent.invoke({"input": "Calcula la suma."})

        self.assertEqual(result["output"], "La suma es 12.")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-local-model")
        self.assertFalse(hasattr(agent, "tools"))
        self.assertIn("January", payload["messages"][0]["content"])

    def test_agent_rejects_csv_paths_outside_the_upload_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outside_csv = Path(temp_dir) / "outside.csv"
            outside_csv.write_text("value\n1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "data/uploads"):
                LocalCsvAnalyst(outside_csv)

    def test_dotenv_loader_reads_only_local_ollama_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "OLLAMA_MODEL=qwen3:1.7b\n"
                "GEMINI_API_KEY=must-not-load\n"
                "OPENAI_API_KEY=must-not-load\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                load_local_config(env_file)

                self.assertEqual(os.environ["OLLAMA_MODEL"], "qwen3:1.7b")
                self.assertNotIn("GEMINI_API_KEY", os.environ)
                self.assertNotIn("OPENAI_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
