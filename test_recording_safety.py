"""Recorder safety-cap and session-ownership tests (issue #25).

The dictation and assistant pipelines share a single Recorder. In hold mode a
lost key-release event used to leave the mic recording with no maximum
duration, and accumulated audio could leak from one session/mode into another.
These tests pin the fixes: a safety cap that applies in hold mode too, stale
timers that self-cancel, and ownership that discards overlapping sessions.

Run:  python -m unittest test_recording_safety -v
"""

import unittest
from unittest.mock import Mock, patch

import main


class _RecordingBase(unittest.TestCase):
    """Mock the shared recorder/UI singletons and reset ownership globals."""

    def setUp(self):
        self.recorder = Mock()
        self.tray = Mock()
        self.widget = Mock()
        self.listener = Mock()
        self._patches = [
            patch.object(main, "recorder", self.recorder),
            patch.object(main, "tray", self.tray),
            patch.object(main, "widget", self.widget),
            patch.object(main, "hotkey_listener", self.listener),
            # Replace the real Timer so _start_timeout never spawns a thread.
            patch.object(main.threading, "Timer", Mock()),
        ]
        for p in self._patches:
            p.start()
        self._reset_globals()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._reset_globals()

    @staticmethod
    def _reset_globals():
        main._active_mode = None
        main._rec_generation = 0
        main._dict_timeout_timer = None
        main._assist_timeout_timer = None


class TestSessionOwnership(_RecordingBase):
    def test_begin_sets_owner_and_bumps_generation(self):
        gen = main._begin_recording("dictation")
        self.assertEqual(gen, 1)
        self.assertEqual(main._active_mode, "dictation")
        self.recorder.start.assert_called_once_with()
        self.assertGreater(main._rec_start, 0)

    def test_normal_stop_returns_audio_and_clears_owner(self):
        self.recorder.stop.return_value = "AUDIO"
        main._begin_recording("dictation")
        audio = main._end_recording("dictation")
        self.assertEqual(audio, "AUDIO")
        self.assertIsNone(main._active_mode)

    def test_stale_stop_is_ignored(self):
        main._begin_recording("dictation")
        self.recorder.stop.reset_mock()
        # A stop for a mode that does not own the recorder must be a no-op.
        result = main._end_recording("assistant")
        self.assertIsNone(result)
        self.recorder.stop.assert_not_called()
        self.assertEqual(main._active_mode, "dictation")

    def test_overlapping_press_discards_stale_session(self):
        # Dictation left running (lost release), then an assistant press.
        main._begin_recording("dictation")
        self.recorder.reset_mock()
        gen2 = main._begin_recording("assistant")
        # The inherited buffer is dropped (stop) before a fresh start.
        self.recorder.stop.assert_called_once_with()
        self.recorder.start.assert_called_once_with()
        self.assertEqual(main._active_mode, "assistant")
        self.assertEqual(gen2, 2)
        # The wedged dictation hotkey flag is reset so it can fire again.
        self.listener.reset_dictation_state.assert_called_once_with()


class TestHoldModeSafetyTimeout(_RecordingBase):
    def test_hold_timeout_discards_audio_and_resets_state(self):
        with patch.object(main.config, "HOLD_TO_RECORD", True):
            gen = main._begin_recording("dictation")
            self.recorder.stop.return_value = "LONG_AUDIO"
            main._timeout_dictation(gen)
        # Mic stopped, but the overrun audio is discarded, not processed.
        self.recorder.stop.assert_called_once_with()
        self.assertIsNone(main._active_mode)
        self.listener.reset_dictation_state.assert_called_once_with()
        self.tray.set_recording.assert_called_with(False)
        self.widget.hide.assert_called_once_with()

    def test_assistant_hold_timeout_discards_and_resets(self):
        with patch.object(main.config, "HOLD_TO_RECORD", True):
            gen = main._begin_recording("assistant")
            main._timeout_assistant(gen)
        self.assertIsNone(main._active_mode)
        self.listener.reset_assistant_state.assert_called_once_with()
        self.widget.hide.assert_called_once_with()

    def test_stale_timer_from_previous_generation_is_noop(self):
        with patch.object(main.config, "HOLD_TO_RECORD", True):
            main._begin_recording("dictation")   # generation 1
            main._end_recording("dictation")     # ends cleanly
            main._begin_recording("dictation")   # generation 2 now active
            self.recorder.reset_mock()
            self.listener.reset_mock()
            # A leftover timer from generation 1 fires late.
            main._timeout_dictation(1)
        self.recorder.stop.assert_not_called()
        self.listener.reset_dictation_state.assert_not_called()
        self.assertEqual(main._active_mode, "dictation")


class TestToggleModeSafetyTimeout(_RecordingBase):
    def test_toggle_timeout_delegates_to_force_stop(self):
        with patch.object(main.config, "HOLD_TO_RECORD", False):
            gen = main._begin_recording("dictation")
            main._timeout_dictation(gen)
        # Toggle mode processes the audio via the listener's normal stop path.
        self.listener.force_stop_dictation.assert_called_once_with()
        # It must not take the hold-mode discard path.
        self.widget.hide.assert_not_called()

    def test_disabled_cap_arms_no_timer(self):
        with patch.object(main.config, "MAX_RECORD_SECONDS", 0):
            main._begin_recording("dictation")
        # MAX_RECORD_SECONDS = 0 disables the safety timer entirely.
        main.threading.Timer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
