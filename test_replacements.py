"""Regression tests for the two-layer replacement engine.

Covers:
- Layer B OFF byte-identity for prose that used to be mangled by the fork
- Layer B ON symbol substitution + single-char/digit collapse
- Contraction safety (never split ``don't``, ``we're``, etc.)
- Layer A user-vocabulary semantics: case-insensitive, whole-word,
  longest-first, applied before Layer B.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import replacements
from replacements import apply_layer_a, apply_layer_b


# ── Regression table (Layer B ON = symbol mode enabled) ───────────────────
_LAYER_B_ON_TABLE = [
    ("I don't know what happened",         "I don't know what happened"),
    ("The 100 meter dash was thrilling",   "The 100 meter - was thrilling"),
    ("It costs one dollar plus tax",       "It costs 1 dollar + tax"),
    ("She is less than happy about it",    "She is < happy about it"),
    ("W H forward slash F A T",            "WH/FAT"),
    # Existing supported patterns
    ("hello W H world",                    "hello WH world"),
    ("one two three dash four five six",   "123-456"),
    ("1 2 3 slash 4 5",                    "123/45"),
    ("we're going home",                   "we're going home"),
    ("it's a test",                        "it's a test"),
]

# ── Layer B OFF: no mutation (byte-identity for prose) ────────────────────
_LAYER_B_OFF_INPUTS = [
    "I don't know what happened",
    "The 100 meter dash was thrilling",
    "It costs one dollar plus tax",
    "No one likes waiting",
    "She is less than happy about it",
    "W H forward slash F A T",
    "hello world",
]


class TestLayerBOff(unittest.TestCase):
    """With Layer B off and no vocabulary, output must equal input."""

    def test_layer_b_off_byte_identity(self):
        for text in _LAYER_B_OFF_INPUTS:
            with self.subTest(text=text):
                # apply_layer_a with empty vocab is inert
                self.assertEqual(apply_layer_a(text, {}), text)


class TestLayerBOn(unittest.TestCase):
    """Regression table for symbol/spelling mode when explicitly enabled."""

    def test_regression_table(self):
        for src, expected in _LAYER_B_ON_TABLE:
            with self.subTest(src=src):
                self.assertEqual(apply_layer_b(src), expected)

    def test_contractions_never_split(self):
        # 'don't' contains apostrophe but must not be broken into chars.
        self.assertIn("don't", apply_layer_b("I don't know"))
        self.assertIn("we're", apply_layer_b("we're happy"))
        self.assertIn("it's", apply_layer_b("it's a test"))

    def test_symbol_between_multichar_words_not_glued(self):
        # 'meter - was' must NOT collapse to 'meter-was'.
        self.assertEqual(apply_layer_b("meter dash was"), "meter - was")

    def test_symbol_between_single_chars_is_glued(self):
        self.assertEqual(apply_layer_b("A forward slash B"), "A/B")

    def test_symbol_between_digits_is_glued(self):
        self.assertEqual(apply_layer_b("123 slash 45"), "123/45")


class TestLayerAVocabulary(unittest.TestCase):
    def test_case_insensitive_whole_word(self):
        vocab = {"hello": "HELLO"}
        self.assertEqual(apply_layer_a("Hello world", vocab), "HELLO world")
        self.assertEqual(apply_layer_a("HELLO world", vocab), "HELLO world")
        # Substring inside another word must NOT match.
        self.assertEqual(apply_layer_a("shellohello world", vocab),
                         "shellohello world")

    def test_multi_word_spoken_form(self):
        vocab = {"kilobit per second": "kbps"}
        self.assertEqual(
            apply_layer_a("The speed was one kilobit per second", vocab),
            "The speed was one kbps",
        )

    def test_longest_first(self):
        # Both "new york" and "new" match; the longer must win.
        vocab = {"new": "N", "new york": "NYC"}
        self.assertEqual(apply_layer_a("I live in new york today", vocab),
                         "I live in NYC today")

    def test_empty_vocab_is_inert(self):
        self.assertEqual(apply_layer_a("anything here", {}), "anything here")

    def test_written_form_can_contain_symbols(self):
        vocab = {"pi": "3.14159"}
        self.assertEqual(apply_layer_a("pi is a constant", vocab),
                         "3.14159 is a constant")


class TestApplyReplacementsPipeline(unittest.TestCase):
    """End-to-end: Layer A then Layer B, ordering matters."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._db = os.path.join(self._tmp, "test.db")
        self._patch = patch("database.DB_PATH", self._db)
        self._patch.start()
        import database
        database.init()
        self.db = database

    def tearDown(self):
        self._patch.stop()

    def test_factory_defaults_are_byte_identical(self):
        # No vocab, symbol mode off (default) — output equals input trimmed.
        for text in _LAYER_B_OFF_INPUTS:
            with self.subTest(text=text):
                self.assertEqual(replacements.apply_replacements(text), text)

    def test_layer_a_runs_before_layer_b(self):
        # Vocab replaces "kilobit per second" → "kbps"; layer B then substitutes
        # "plus" → "+" and glues around single chars only.
        self.db.save_vocabulary_entry("kilobit per second", "kbps")
        self.db.save_setting("symbol_mode", "1")
        out = replacements.apply_replacements(
            "The speed is one kilobit per second plus overhead")
        # After Layer A: "The speed is one kbps plus overhead"
        # After Layer B: "one"→"1", "plus"→"+", but "+" between multi-char
        # words ("kbps"/"overhead") stays spaced.
        self.assertEqual(out, "The speed is 1 kbps + overhead")

    def test_vocabulary_is_empty_when_no_entries(self):
        self.assertEqual(replacements._load_vocab(), {})

    def test_priming_prompt_empty_when_no_terms(self):
        self.assertIsNone(replacements.get_initial_prompt())

    def test_priming_prompt_joins_terms(self):
        self.db.replace_priming_terms(["kubernetes", "Postgres", "gRPC"])
        prompt = replacements.get_initial_prompt()
        self.assertIsNotNone(prompt)
        for term in ("kubernetes", "Postgres", "gRPC"):
            self.assertIn(term, prompt)


if __name__ == "__main__":
    unittest.main()
