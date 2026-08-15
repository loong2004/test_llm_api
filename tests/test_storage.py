import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_tester.models import Protocol, Provider
from llm_tester.storage import ProviderRepository, app_data_dir, runtime_dir


class StoragePathTests(unittest.TestCase):
    def test_provider_converts_protocol_strings_to_enum(self):
        provider = Provider("Local", "https://example.com/v1", "openai")
        self.assertEqual(provider.protocol, Protocol.OPENAI)

    def test_frozen_app_uses_data_directory_next_to_bundle(self):
        executable = "/Applications/LLM API Lab.app/Contents/MacOS/LLM API Lab"
        with patch("llm_tester.storage.sys.frozen", True, create=True), patch(
            "llm_tester.storage.sys.executable", executable
        ):
            self.assertEqual(runtime_dir(), Path("/Applications"))
            self.assertEqual(app_data_dir(), Path("/Applications/data"))

    def test_repository_writes_provider_json_to_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            repository = ProviderRepository(data_dir / "providers.json")
            provider = Provider(
                "Local", "https://example.com/v1", Protocol.OPENAI, ["example-model"], "plain-api-key"
            )
            repository.save_all([provider])

            self.assertTrue(repository.path.exists())
            raw = json.loads(repository.path.read_text(encoding="utf-8"))
            self.assertEqual(raw["providers"][0]["api_key"], "plain-api-key")
            loaded = repository.list()
            self.assertEqual(loaded[0].name, "Local")
            self.assertEqual(loaded[0].models, ["example-model"])
            self.assertEqual(loaded[0].api_key, "plain-api-key")
