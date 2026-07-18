"""Hotkey serialisation and conflict-detection tests.

Covers the acceptance criterion "hotkey combo round-trip and conflict
detection" for the fork's combo-hotkey feature.
"""

import threading
import unittest
from unittest.mock import patch

from pynput.keyboard import Key, KeyCode

from hotkey import HotkeyListener
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


class TestFailedStartReset(unittest.TestCase):
    def test_cancel_dictation_start_resets_toggle_and_hold_state(self):
        listener = HotkeyListener(lambda: None, lambda: None)
        listener._dict_recording = True
        listener._dict_pressed = True

        listener.cancel_dictation_start()

        self.assertFalse(listener._dict_recording)
        self.assertFalse(listener._dict_pressed)

    def test_cancel_assistant_start_resets_toggle_and_hold_state(self):
        listener = HotkeyListener(lambda: None, lambda: None)
        listener._assist_recording = True
        listener._assist_pressed = True

        listener.cancel_assistant_start()

        self.assertFalse(listener._assist_recording)
        self.assertFalse(listener._assist_pressed)


class TestCallbackDispatch(unittest.TestCase):
    def test_slow_start_does_not_prevent_release_from_being_queued(self):
        start_entered = threading.Event()
        allow_start_to_finish = threading.Event()
        release_called = threading.Event()

        def slow_start():
            start_entered.set()
            allow_start_to_finish.wait(timeout=1)

        listener = HotkeyListener(slow_start, release_called.set)
        listener._safe_call(slow_start, "start")
        self.assertTrue(start_entered.wait(timeout=0.2))

        listener._safe_call(release_called.set, "release")
        self.assertFalse(release_called.is_set())
        allow_start_to_finish.set()

        self.assertTrue(release_called.wait(timeout=0.2))
        listener.stop()

    def test_stop_waits_for_running_callback(self):
        callback_entered = threading.Event()
        allow_callback_to_finish = threading.Event()

        def blocked_callback():
            callback_entered.set()
            allow_callback_to_finish.wait(timeout=1)

        listener = HotkeyListener(blocked_callback, lambda: None)
        listener._safe_call(blocked_callback, "blocked")
        self.assertTrue(callback_entered.wait(timeout=0.2))

        stopper = threading.Thread(target=listener.stop)
        stopper.start()
        self.assertTrue(stopper.is_alive())
        allow_callback_to_finish.set()
        stopper.join(timeout=0.2)

        self.assertFalse(stopper.is_alive())
        self.assertFalse(listener._callback_worker.is_alive())

    @patch("hotkey.keyboard.Listener")
    def test_start_after_stop_does_not_create_keyboard_listener(
            self, keyboard_listener):
        listener = HotkeyListener(lambda: None, lambda: None)
        listener.stop()

        listener.start()

        keyboard_listener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
