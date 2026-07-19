"""Provider adapter tests for the local LLM assistant."""

import unittest
from unittest.mock import Mock, patch

import assistant
import config


class TestOpenAICompatibleProvider(unittest.TestCase):
    def setUp(self):
        self._config = patch.multiple(
            config,
            ASSISTANT_PROVIDER="openai",
            OPENAI_URL="http://localhost:8080/v1/",
            OPENAI_MODEL="local-test-model",
            OPENAI_API_KEY="",
        )
        self._config.start()

    def tearDown(self):
        self._config.stop()

    @patch.object(assistant, "_system_prompt", return_value="system prompt")
    @patch.object(assistant.requests, "post")
    def test_chat_completion_tool_call_is_normalized(self, post, _prompt):
        response = Mock()
        response.json.return_value = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "save_note",
                            "arguments": '{"content":"buy milk"}',
                        },
                    }],
                },
            }],
        }
        post.return_value = response

        result = assistant._call_openai("remember to buy milk")

        self.assertEqual(result, {
            "function": "save_note",
            "arguments": {"content": "buy milk"},
        })
        response.raise_for_status.assert_called_once_with()
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(url, "http://localhost:8080/v1/chat/completions")
        self.assertEqual(kwargs["json"]["model"], "local-test-model")
        self.assertEqual(kwargs["json"]["messages"][0]["content"],
                         "system prompt")
        self.assertEqual(kwargs["json"]["messages"][1], {
            "role": "user",
            "content": "remember to buy milk",
        })
        self.assertIs(kwargs["json"]["tools"], assistant.TOOLS)
        self.assertNotIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["timeout"], 120)

    @patch.object(assistant.requests, "post")
    def test_invalid_tool_arguments_are_rejected(self, post):
        response = Mock()
        response.json.return_value = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "save_note",
                            "arguments": "not json",
                        },
                    }],
                },
            }],
        }
        post.return_value = response

        self.assertIsNone(assistant._call_openai("remember this"))

    @patch.object(assistant.requests, "post")
    def test_object_tool_arguments_are_also_accepted(self, post):
        response = Mock()
        response.json.return_value = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "save_note",
                            "arguments": {"content": "already decoded"},
                        },
                    }],
                },
            }],
        }
        post.return_value = response

        self.assertEqual(assistant._call_openai("remember this"), {
            "function": "save_note",
            "arguments": {"content": "already decoded"},
        })

    @patch.object(assistant.requests, "get")
    def test_health_check_uses_models_endpoint_and_api_key(self, get):
        config.OPENAI_API_KEY = "local-secret"
        get.return_value.status_code = 200

        self.assertTrue(assistant.ping_provider())

        get.assert_called_once_with(
            "http://localhost:8080/v1/models",
            headers={"Authorization": "Bearer local-secret"},
            timeout=2,
        )


class TestProviderDispatch(unittest.TestCase):
    @patch.object(assistant, "_call_openai", return_value={"provider": "openai"})
    def test_openai_provider_is_selected(self, call_openai):
        with patch.object(config, "ASSISTANT_PROVIDER", "openai"):
            self.assertEqual(assistant._call_provider("hello"),
                             {"provider": "openai"})
        call_openai.assert_called_once_with("hello")

    @patch.object(assistant, "_call_ollama", return_value={"provider": "ollama"})
    def test_ollama_remains_the_default(self, call_ollama):
        with patch.object(config, "ASSISTANT_PROVIDER", "ollama"):
            self.assertEqual(assistant._call_provider("hello"),
                             {"provider": "ollama"})
        call_ollama.assert_called_once_with("hello")


if __name__ == "__main__":
    unittest.main()
