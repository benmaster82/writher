"""Hotkey serialization, conflict-detection, safety-state, and Alt-mask tests.

Run from the project directory:
    python -m unittest test_hotkey -v

The Alt-mask tests mock timers and keyboard input. They verify the Python
workaround's behavior, but do not prove that Windows apps stop opening menus.
"""

import unittest
from unittest.mock import Mock, patch

from pynput.keyboard import Key, KeyCode

import config
import hotkey
from hotkey import HotkeyListener
from hotkey_util import (
    key_to_str,
    str_to_key,
    hotkeys_equal,
    keys_match,
    canonical_modifier,
    is_blocked,
)


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
        self.assertFalse(
            hotkeys_equal(
                Key.alt_gr,
                (frozenset({"ctrl"}), KeyCode.from_vk(82)),
            )
        )

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
        self.assertFalse(
            is_blocked((frozenset({"ctrl"}), KeyCode.from_char("a")))
        )


class TestBareModifierHotkeys(unittest.TestCase):
    """Regression tests for issue #19: bare modifiers as hotkeys."""

    def _listener(self):
        cbs = {
            name: Mock()
            for name in ("press", "release", "assist_press", "assist_release")
        }
        listener = HotkeyListener(
            on_press_cb=cbs["press"],
            on_release_cb=cbs["release"],
            on_assist_press_cb=cbs["assist_press"],
            on_assist_release_cb=cbs["assist_release"],
        )
        return listener, cbs

    def test_right_ctrl_hotkey_fires_in_hold_mode(self):
        with patch.multiple(config, HOTKEY=Key.ctrl_r, HOLD_TO_RECORD=True):
            listener, cbs = self._listener()
            listener._handle_press(Key.ctrl_r)
            cbs["press"].assert_called_once_with()
            listener._handle_release(Key.ctrl_r)
            cbs["release"].assert_called_once_with()

    def test_other_ctrl_variant_does_not_fire(self):
        with patch.multiple(config, HOTKEY=Key.ctrl_r, HOLD_TO_RECORD=True):
            listener, cbs = self._listener()
            listener._handle_press(Key.ctrl_l)
            cbs["press"].assert_not_called()
            # It is still tracked as a held modifier.
            self.assertIn("ctrl", listener._held_modifiers)

    def test_right_ctrl_hotkey_toggles_in_toggle_mode(self):
        with patch.multiple(config, HOTKEY=Key.ctrl_r, HOLD_TO_RECORD=False):
            listener, cbs = self._listener()
            listener._handle_press(Key.ctrl_r)
            cbs["press"].assert_called_once_with()
            listener._dict_last_toggle = 0.0  # bypass debounce
            listener._handle_press(Key.ctrl_r)
            cbs["release"].assert_called_once_with()

    def test_bare_modifier_assistant_hotkey_fires(self):
        with patch.multiple(
            config, ASSISTANT_HOTKEY=Key.ctrl_r, HOLD_TO_RECORD=True
        ):
            listener, cbs = self._listener()
            listener._handle_press(Key.ctrl_r)
            cbs["assist_press"].assert_called_once_with()

    def test_combo_hotkey_still_works_alongside_bare_modifier(self):
        combo = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        with patch.multiple(
            config,
            HOTKEY=Key.shift_r,
            ASSISTANT_HOTKEY=combo,
            HOLD_TO_RECORD=True,
        ):
            listener, cbs = self._listener()
            listener._handle_press(Key.ctrl_l)
            listener._handle_press(Key.alt_l)
            listener._handle_press(KeyCode.from_vk(82))
            cbs["assist_press"].assert_called_once_with()
            cbs["press"].assert_not_called()

    def test_conflict_with_combo_modifier_is_logged(self):
        combo = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))
        with patch.multiple(config, HOTKEY=Key.ctrl_r, ASSISTANT_HOTKEY=combo):
            listener, _ = self._listener()
            with patch.object(hotkey, "log") as mock_log:
                listener._warn_bare_modifier_conflicts()
            mock_log.warning.assert_called_once()

    def test_no_conflict_warning_for_disjoint_hotkeys(self):
        combo = (frozenset({"shift", "alt"}), KeyCode.from_vk(82))
        with patch.multiple(config, HOTKEY=Key.ctrl_r, ASSISTANT_HOTKEY=combo):
            listener, _ = self._listener()
            with patch.object(hotkey, "log") as mock_log:
                listener._warn_bare_modifier_conflicts()
            mock_log.warning.assert_not_called()


class TestSafetyStateReset(unittest.TestCase):
    """Issue #25: the safety timeout must un-wedge a stuck hold-mode flag."""

    def _listener(self):
        cbs = {
            name: Mock()
            for name in ("press", "release", "assist_press", "assist_release")
        }
        listener = HotkeyListener(
            on_press_cb=cbs["press"],
            on_release_cb=cbs["release"],
            on_assist_press_cb=cbs["assist_press"],
            on_assist_release_cb=cbs["assist_release"],
        )
        return listener, cbs

    def test_reset_dictation_clears_flags_without_callback(self):
        listener, cbs = self._listener()
        listener._dict_pressed = True
        listener._dict_recording = True
        listener.reset_dictation_state()
        self.assertFalse(listener._dict_pressed)
        self.assertFalse(listener._dict_recording)
        cbs["release"].assert_not_called()

    def test_reset_assistant_clears_flags_without_callback(self):
        listener, cbs = self._listener()
        listener._assist_pressed = True
        listener._assist_recording = True
        listener.reset_assistant_state()
        self.assertFalse(listener._assist_pressed)
        self.assertFalse(listener._assist_recording)
        cbs["assist_release"].assert_not_called()

    @patch("hotkey.threading.Timer")
    @patch("hotkey.Controller")
    def test_press_fires_again_after_reset(self, controller_class, timer_class):
        # A stuck _dict_pressed swallows presses; reset restores the hotkey.
        # Mock the timer and keyboard controller because AltGr now triggers the
        # masking workaround, which must not send real OS keyboard events here.
        with patch.multiple(config, HOTKEY=Key.alt_gr, HOLD_TO_RECORD=True):
            listener, cbs = self._listener()
            listener._dict_pressed = True  # simulate a lost key-release
            listener._handle_press(Key.alt_gr)
            cbs["press"].assert_not_called()  # wedged

            listener.reset_dictation_state()
            listener._handle_press(Key.alt_gr)
            cbs["press"].assert_called_once_with()  # recovered

        timer_class.assert_called_once_with(
            hotkey._MASK_DELAY_SEC, listener._send_dummy
        )
        timer_class.return_value.start.assert_called_once_with()
        controller_class.assert_called_once_with()
        listener._kb.press.assert_not_called()
        listener._kb.release.assert_not_called()


class TestAltMask(unittest.TestCase):
    """Unit tests for the Alt/AltGr dummy-key workaround."""

    def _listener(self):
        cbs = {
            name: Mock()
            for name in ("press", "release", "assist_press", "assist_release")
        }
        # Mock Controller before constructing HotkeyListener, so no real OS
        # keyboard controller is instantiated during these unit tests.
        with patch("hotkey.Controller", return_value=Mock()):
            listener = HotkeyListener(
                on_press_cb=cbs["press"],
                on_release_cb=cbs["release"],
                on_assist_press_cb=cbs["assist_press"],
                on_assist_release_cb=cbs["assist_release"],
            )
        return listener, cbs

    @patch("hotkey.threading.Timer")
    def test_altgr_schedules_dummy_timer(self, timer_class):
        listener, _ = self._listener()

        listener._mask_alt_tap(Key.alt_gr)

        timer_class.assert_called_once_with(
            hotkey._MASK_DELAY_SEC, listener._send_dummy
        )
        timer = timer_class.return_value
        self.assertTrue(timer.daemon)
        timer.start.assert_called_once_with()
        self.assertTrue(listener._mask_pending)

    @patch("hotkey.threading.Timer")
    def test_each_supported_alt_key_can_schedule_timer(self, timer_class):
        for alt_key in hotkey._ALT_KEYS:
            with self.subTest(key=alt_key):
                timer_class.reset_mock()
                listener, _ = self._listener()
                listener._mask_alt_tap(alt_key)
                timer_class.assert_called_once_with(
                    hotkey._MASK_DELAY_SEC, listener._send_dummy
                )

    @patch("hotkey.threading.Timer")
    def test_non_alt_key_does_not_schedule_timer(self, timer_class):
        listener, _ = self._listener()

        listener._mask_alt_tap(KeyCode.from_char("a"))

        timer_class.assert_not_called()
        self.assertFalse(listener._mask_pending)

    @patch("hotkey.threading.Timer")
    def test_pending_flag_prevents_duplicate_timers(self, timer_class):
        listener, _ = self._listener()

        listener._mask_alt_tap(Key.alt_gr)
        listener._mask_alt_tap(Key.alt_gr)
        listener._mask_alt_tap(Key.alt_r)

        timer_class.assert_called_once()
        self.assertTrue(listener._mask_pending)

    def test_send_dummy_presses_and_releases_expected_key(self):
        listener, _ = self._listener()
        listener._mask_pending = True
        listener._sign.set()  # _send_dummy exits early unless the listener is started

        listener._send_dummy()

        expected_dummy = KeyCode.from_vk(hotkey._DUMMY_VK)
        listener._kb.press.assert_called_once_with(expected_dummy)
        listener._kb.release.assert_called_once_with(expected_dummy)
        self.assertFalse(listener._mask_pending)

    def test_pending_flag_resets_if_dummy_press_raises(self):
        listener, _ = self._listener()
        listener._mask_pending = True
        listener._sign.set()  # allow _send_dummy to reach the error-handling path
        listener._kb.press.side_effect = RuntimeError("simulated keyboard error")

        with patch.object(hotkey, "log") as mock_log:
            listener._send_dummy()

        mock_log.error.assert_called_once()
        self.assertFalse(listener._mask_pending)
        listener._kb.release.assert_not_called()

    @patch("hotkey.threading.Timer")
    def test_configured_altgr_hotkey_invokes_masking_and_dictation(
        self, timer_class
    ):
        listener, cbs = self._listener()

        with patch.multiple(
            config,
            HOTKEY=Key.alt_gr,
            ASSISTANT_HOTKEY=Key.f9,
            HOLD_TO_RECORD=True,
        ):
            listener._handle_press(Key.alt_gr)

        timer_class.assert_called_once_with(
            hotkey._MASK_DELAY_SEC, listener._send_dummy
        )
        cbs["press"].assert_called_once_with()
        self.assertTrue(listener._dict_pressed)

    @patch("hotkey.threading.Timer")
    def test_unmatched_alt_key_does_not_schedule_mask_timer(self, timer_class):
        listener, cbs = self._listener()

        with patch.multiple(
            config,
            HOTKEY=Key.f9,
            ASSISTANT_HOTKEY=Key.f10,
            HOLD_TO_RECORD=True,
        ):
            listener._handle_press(Key.alt_gr)

        timer_class.assert_not_called()
        cbs["press"].assert_not_called()
        cbs["assist_press"].assert_not_called()

    @patch("hotkey.threading.Timer")
    def test_stop_cancels_pending_mask_timer_and_prevents_late_key_event(
        self, timer_class
    ):
        listener, _ = self._listener()
        listener._sign.set()  # simulate a started listener without starting OS hooks

        listener._mask_alt_tap(Key.alt_gr)

        timer_class.assert_called_once_with(
            hotkey._MASK_DELAY_SEC, listener._send_dummy
        )
        timer = timer_class.return_value
        self.assertTrue(listener._mask_pending)
        self.assertIs(listener._alarm, timer)

        # Shutdown must cancel the pending timer and clear its state.
        listener.stop()

        timer.cancel.assert_called_once_with()
        self.assertFalse(listener._sign.is_set())
        self.assertFalse(listener._mask_pending)

        # Exercise the race where a timer callback was already dispatched when
        # cancellation happened. It must not send keyboard input after stop().
        listener._send_dummy()
        listener._kb.press.assert_not_called()
        listener._kb.release.assert_not_called()


if __name__ == "__main__":
    unittest.main()