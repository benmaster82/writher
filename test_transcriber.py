import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from transcriber import Transcriber


class TranscriberInfoTests(unittest.TestCase):
    @patch("transcriber.log")
    @patch("transcriber.config.WHISPER_LANGUAGE", None)
    @patch("transcriber.get_initial_prompt", return_value="")
    def test_transcribe_with_info_returns_detected_language(
            self, _prompt, mocked_log):
        transcriber = Transcriber.__new__(Transcriber)
        segment = SimpleNamespace(text=" hello ")
        info = SimpleNamespace(language="en", language_probability=0.92)
        transcriber._model = MagicMock()
        transcriber._model.transcribe.return_value = ([segment], info)

        text, language, probability = transcriber.transcribe_with_info(
            np.zeros(100, dtype=np.float32))

        self.assertEqual(text, "hello")
        self.assertEqual(language, "en")
        self.assertEqual(probability, 0.92)
        mocked_log.info.assert_any_call(
            "Language detection: enabled (Auto).")

    @patch("transcriber.log")
    @patch("transcriber.config.WHISPER_LANGUAGE", "lt")
    @patch("transcriber.get_initial_prompt", return_value="")
    def test_fixed_language_is_logged_and_detection_is_skipped(
            self, _prompt, mocked_log):
        transcriber = Transcriber.__new__(Transcriber)
        transcriber._model = MagicMock()
        transcriber._model.transcribe.return_value = (
            [SimpleNamespace(text=" labas ")],
            SimpleNamespace(language="lt", language_probability=1.0),
        )

        text, language, _ = transcriber.transcribe_with_info(
            np.zeros(100, dtype=np.float32))

        self.assertEqual((text, language), ("labas", "lt"))
        self.assertEqual(
            transcriber._model.transcribe.call_args.kwargs["language"], "lt")
        mocked_log.info.assert_any_call(
            "Language detection: disabled; using fixed language: %s.", "lt")
        self.assertFalse(any(
            call.args and call.args[0].startswith("Whisper detected language")
            for call in mocked_log.info.call_args_list
        ))

    @patch.object(Transcriber, "transcribe_with_info")
    def test_transcribe_keeps_string_api(self, transcribe_with_info):
        transcribe_with_info.return_value = ("hello", "en", 0.92)
        transcriber = Transcriber.__new__(Transcriber)

        self.assertEqual(
            transcriber.transcribe(np.zeros(10, dtype=np.float32)), "hello")


if __name__ == "__main__":
    unittest.main()
