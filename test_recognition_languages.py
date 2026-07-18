import unittest

from recognition_languages import (
    SUPPORTED_LANGUAGE_CODES,
    language_display_name,
)


class RecognitionLanguageTests(unittest.TestCase):
    def test_whisper_language_list_is_not_artificially_limited(self):
        self.assertGreaterEqual(len(SUPPORTED_LANGUAGE_CODES), 90)
        self.assertIn("lt", SUPPORTED_LANGUAGE_CODES)
        self.assertIn("ja", SUPPORTED_LANGUAGE_CODES)

    def test_windows_resolves_common_language_name(self):
        self.assertEqual(language_display_name("lt"), "Lithuanian (LT)")

    def test_unknown_language_falls_back_to_code(self):
        self.assertEqual(language_display_name("not-a-language"), "NOT-A-LANGUAGE")


if __name__ == "__main__":
    unittest.main()
