"""Settings tests for switching between local assistant providers."""

import unittest
from unittest.mock import Mock, patch

import config
import settings_window


class TestAssistantModelDiscovery(unittest.TestCase):
    @patch("requests.get")
    def test_openai_compatible_models_are_read_from_data(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            "data": [{"id": "local-a"}, {"id": "local-b"}],
        }
        with patch.multiple(
            config,
            OPENAI_URL="http://localhost:8080/v1/",
            OPENAI_API_KEY="",
        ):
            models = settings_window._fetch_assistant_models("openai")

        self.assertEqual(models, ["local-a", "local-b"])
        get.assert_called_once_with(
            "http://localhost:8080/v1/models", headers={}, timeout=5)

    @patch("requests.get")
    def test_ollama_models_keep_existing_response_format(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            "models": [{"name": "llama3.1:8b"}],
        }
        with patch.object(config, "OLLAMA_URL", "http://localhost:11434/"):
            models = settings_window._fetch_assistant_models("ollama")

        self.assertEqual(models, ["llama3.1:8b"])
        get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)


class TestAssistantSettingsPersistence(unittest.TestCase):
    def setUp(self):
        self.window = object.__new__(settings_window.SettingsWindow)
        self.window._root = Mock()
        self.window._root.after.side_effect = lambda _delay, callback: callback()
        self.window._win = Mock()
        self.window._assistant_model_dropdown = Mock()
        self.window._assistant_url_entry = Mock()

    @patch.object(settings_window.db, "save_setting")
    @patch.object(settings_window, "_fetch_assistant_models",
                  return_value=["loaded-model"])
    def test_first_discovered_openai_model_replaces_empty_default(
            self, _fetch, save):
        with patch.multiple(
            config,
            ASSISTANT_PROVIDER="openai",
            OPENAI_MODEL="",
        ):
            self.window._fetch_and_update_assistant_models("openai")

            self.assertEqual(config.OPENAI_MODEL, "loaded-model")
            self.window._assistant_model_dropdown.configure.assert_called_once_with(
                values=["loaded-model"])
            self.window._assistant_model_dropdown.set.assert_called_once_with(
                "loaded-model")
        save.assert_called_once_with("openai_model", "loaded-model")

    @patch.object(settings_window.db, "save_setting")
    @patch.object(settings_window, "_fetch_assistant_models",
                  return_value=["discovered-model"])
    def test_manual_openai_model_is_preserved_when_not_discovered(
            self, _fetch, save):
        with patch.multiple(
            config,
            ASSISTANT_PROVIDER="openai",
            OPENAI_MODEL="manual-alias",
        ):
            self.window._fetch_and_update_assistant_models("openai")

            self.assertEqual(config.OPENAI_MODEL, "manual-alias")
            self.window._assistant_model_dropdown.configure.assert_called_once_with(
                values=["manual-alias", "discovered-model"])
            self.window._assistant_model_dropdown.set.assert_called_once_with(
                "manual-alias")
        save.assert_not_called()

    @patch.object(settings_window.threading, "Thread")
    @patch.object(settings_window.db, "save_setting")
    def test_switching_provider_loads_its_separate_values(self, save, thread):
        with patch.multiple(
            config,
            ASSISTANT_PROVIDER="ollama",
            OPENAI_MODEL="local-model",
            OPENAI_URL="http://localhost:8080/v1",
        ):
            self.window._on_assistant_provider_change("OpenAI-compatible")

            self.assertEqual(config.ASSISTANT_PROVIDER, "openai")
            self.window._assistant_model_dropdown.set.assert_called_with(
                "local-model")
            self.window._assistant_url_entry.insert.assert_called_with(
                0, "http://localhost:8080/v1")
        save.assert_called_once_with("assistant_provider", "openai")
        thread.return_value.start.assert_called_once_with()

    @patch.object(settings_window.threading, "Thread")
    @patch.object(settings_window.db, "save_setting")
    def test_openai_url_does_not_overwrite_ollama_url(self, save, thread):
        self.window._assistant_url_entry.get.return_value = (
            "http://localhost:9090/v1")
        with patch.multiple(
            config,
            ASSISTANT_PROVIDER="openai",
            OPENAI_URL="http://localhost:8080/v1",
            OLLAMA_URL="http://localhost:11434",
        ):
            self.window._on_assistant_url_change()

            self.assertEqual(config.OPENAI_URL, "http://localhost:9090/v1")
            self.assertEqual(config.OLLAMA_URL, "http://localhost:11434")
        save.assert_called_once_with("openai_url", "http://localhost:9090/v1")
        thread.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
