"""Hotkey serialisation and conflict-detection tests.

Covers the acceptance criterion "hotkey combo round-trip and conflict
detection" for the fork's combo-hotkey feature.
"""

import unittest

from pynput.keyboard import Key, KeyCode

from hotkey_util import (key_to_str, str_to_key, hotkeys_equal, keys_match,
                        canonical_modifier, is_blocked)


class TestSingleKeyRoundTrip(unittest.TestCase):
    def test_alt_gr_round_trip(self):
        s = key_to_str(Key.alt_gr)
        parsed = str_to_key(s)
        self.assertTrue(keys_match(parsed, Key.alt_gr))

    def test_keycode_by_vk_round_trip(self):
        original = KeyCode.from_vk(82)  # R key
        s = key_to_str(original)
        parsed = str_to_key(s)
        self.assertTrue(keys_match(parsed, original))


class TestComboRoundTrip(unittest.TestCase):
    def test_ctrl_alt_r_round_trip(self):
        combo = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        s = key_to_str(combo)
        parsed = str_to_key(s)
        self.assertIsInstance(parsed, tuple)
        mods, trigger = parsed
        self.assertEqual(mods, frozenset({"ctrl", "alt"}))
        self.assertTrue(keys_match(trigger, KeyCode.from_vk(82)))

    def test_ctrl_shift_f9_round_trip(self):
        combo = (frozenset({"ctrl", "shift"}), Key.f9)
        s = key_to_str(combo)
        parsed = str_to_key(s)
        self.assertIsInstance(parsed, tuple)
        mods, trigger = parsed
        self.assertEqual(mods, frozenset({"ctrl", "shift"}))
        self.assertEqual(trigger, Key.f9)


class TestConflictDetection(unittest.TestCase):
    def test_same_combo_conflicts(self):
        a = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        b = (frozenset({"alt", "ctrl"}), KeyCode.from_vk(82))
        self.assertTrue(hotkeys_equal(a, b))

    def test_different_trigger_no_conflict(self):
        a = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        b = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(83))
        self.assertFalse(hotkeys_equal(a, b))

    def test_different_modifiers_no_conflict(self):
        a = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        b = (frozenset({"ctrl", "shift"}), KeyCode.from_vk(82))
        self.assertFalse(hotkeys_equal(a, b))

    def test_single_vs_combo_no_conflict(self):
        self.assertFalse(hotkeys_equal(
            Key.alt_gr,
            (frozenset({"ctrl"}), KeyCode.from_vk(82)),
        ))

    def test_single_key_conflict(self):
        self.assertTrue(hotkeys_equal(Key.alt_gr, Key.alt_gr))


class TestModifierClassification(unittest.TestCase):
    def test_ctrl_variants_map_to_ctrl(self):
        self.assertEqual(canonical_modifier(Key.ctrl), "ctrl")
        self.assertEqual(canonical_modifier(Key.ctrl_l), "ctrl")
        self.assertEqual(canonical_modifier(Key.ctrl_r), "ctrl")

    def test_alt_gr_is_not_a_modifier(self):
        # AltGr is intentionally treated as a trigger, not a modifier.
        self.assertIsNone(canonical_modifier(Key.alt_gr))


class TestBlockedKeys(unittest.TestCase):
    def test_enter_is_blocked(self):
        self.assertTrue(is_blocked(Key.enter))

    def test_alphanumeric_key_alone_is_blocked(self):
        # Bare "a" without modifiers is blocked to avoid capturing typing.
        self.assertTrue(is_blocked(KeyCode.from_char("a")))

    def test_combo_never_blocked(self):
        # Any combo is allowed, even if the trigger would be blocked alone.
        self.assertFalse(is_blocked(
            (frozenset({"ctrl"}), KeyCode.from_char("a"))
        ))


if __name__ == "__main__":
    unittest.main()
