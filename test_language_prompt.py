import unittest
from unittest.mock import MagicMock, patch

import config
import main


class LanguagePromptTests(unittest.TestCase):
    def setUp(self):
        self.original_language = config.WHISPER_LANGUAGE
        self.original_widget = main.widget
        self.original_pending = main._language_prompt_pending
        self.original_detected = main._last_detected_language
        config.WHISPER_LANGUAGE = None
        main.widget = MagicMock()
        main._language_prompt_pending = False
        main._last_detected_language = None

    def tearDown(self):
        config.WHISPER_LANGUAGE = self.original_language
        main.widget = self.original_widget
        main._language_prompt_pending = self.original_pending
        main._last_detected_language = self.original_detected

    @patch.object(main.db, "get_setting", return_value="0")
    def test_any_detected_language_can_be_offered(self, _get_setting):
        main._maybe_offer_detected_language("lt")

        self.assertEqual(main._last_detected_language, "lt")
        args = main.widget.show_language_prompt.call_args.args
        self.assertIn("Lithuanian (LT)", args[0])
        self.assertIn("Lithuanian (LT)", args[1])

    @patch.object(main.db, "get_setting", return_value="0")
    def test_unsupported_detected_language_is_ignored(self, _get_setting):
        main._maybe_offer_detected_language("not-a-language")

        main.widget.show_language_prompt.assert_not_called()
        self.assertIsNone(main._last_detected_language)

    @patch.object(main.db, "save_settings")
    @patch.object(main.db, "get_setting", return_value="0")
    def test_accept_saves_detected_language(self, _get_setting, save_settings):
        main._maybe_offer_detected_language("ja")
        accept = main.widget.show_language_prompt.call_args.args[3]

        accept()

        self.assertEqual(config.WHISPER_LANGUAGE, "ja")
        save_settings.assert_called_once_with({
            "whisper_language": "ja",
            "auto_language_prompt_answered": "1",
        })

    @patch.object(main.db, "save_setting")
    @patch.object(main.db, "get_setting", return_value="0")
    def test_decline_keeps_auto_and_suppresses_future_prompt(
            self, _get_setting, save_setting):
        main._maybe_offer_detected_language("de")
        decline = main.widget.show_language_prompt.call_args.args[4]

        decline()

        self.assertIsNone(config.WHISPER_LANGUAGE)
        save_setting.assert_called_with("auto_language_prompt_answered", "1")

    @patch.object(main.db, "save_settings", side_effect=OSError("disk full"))
    @patch.object(main.db, "get_setting", return_value="0")
    def test_save_failure_clears_pending_without_fixing_language(
            self, _get_setting, _save_settings):
        main._maybe_offer_detected_language("lt")
        accept = main.widget.show_language_prompt.call_args.args[3]

        accept()

        self.assertIsNone(config.WHISPER_LANGUAGE)
        self.assertFalse(main._language_prompt_pending)


if __name__ == "__main__":
    unittest.main()
