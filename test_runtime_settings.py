"""Runtime configurability of device / compute type / audio cues.

Issue #23: DEVICE and COMPUTE_TYPE selectable from Settings + persisted, so
packaged users can enable CUDA without editing config.py.
Issue #24: the audio-cues toggle persists and updates config.

The Settings callbacks are exercised on a bare SettingsWindow shell (no Tk),
and the startup load path is exercised through main._load_settings.

Run:  python -m unittest test_runtime_settings -v
"""

import unittest
from unittest.mock import Mock, patch

import config
import main
import settings_window


def _window_shell():
    """A SettingsWindow with only the attributes the callbacks touch."""
    w = object.__new__(settings_window.SettingsWindow)
    w._perf_note = Mock()
    w._audio_cues_switch_var = Mock()
    return w


class TestPerformanceSettings(unittest.TestCase):
    @patch.object(settings_window.db, "save_setting")
    def test_device_change_persists_and_flags_restart(self, save):
        w = _window_shell()
        with patch.object(config, "DEVICE", "cpu"):
            w._on_device_change("CUDA (NVIDIA GPU)")
            self.assertEqual(config.DEVICE, "cuda")
        save.assert_called_once_with("device", "cuda")
        w._perf_note.configure.assert_called_once()

    @patch.object(settings_window.db, "save_setting")
    def test_device_change_ignored_when_unchanged(self, save):
        w = _window_shell()
        with patch.object(config, "DEVICE", "cpu"):
            w._on_device_change("CPU")
        save.assert_not_called()
        w._perf_note.configure.assert_not_called()

    @patch.object(settings_window.db, "save_setting")
    def test_compute_change_persists(self, save):
        w = _window_shell()
        with patch.object(config, "COMPUTE_TYPE", "int8"):
            w._on_compute_change("float16")
            self.assertEqual(config.COMPUTE_TYPE, "float16")
        save.assert_called_once_with("compute_type", "float16")


class TestAudioCuesSetting(unittest.TestCase):
    @patch.object(settings_window.db, "save_setting")
    def test_toggle_on_updates_config_and_persists(self, save):
        w = _window_shell()
        w._audio_cues_switch_var.get.return_value = "1"
        with patch.object(config, "AUDIO_CUES", False):
            w._on_audio_cues_toggle()
            self.assertTrue(config.AUDIO_CUES)
        save.assert_called_once_with("audio_cues", "1")

    @patch.object(settings_window.db, "save_setting")
    def test_toggle_off_updates_config_and_persists(self, save):
        w = _window_shell()
        w._audio_cues_switch_var.get.return_value = "0"
        with patch.object(config, "AUDIO_CUES", True):
            w._on_audio_cues_toggle()
            self.assertFalse(config.AUDIO_CUES)
        save.assert_called_once_with("audio_cues", "0")


class TestLoadSettings(unittest.TestCase):
    """main._load_settings applies persisted device/compute/cues to config."""

    def _load_with(self, values):
        def fake_get(key, default=""):
            return values.get(key, "")
        with patch.object(main.db, "get_setting", side_effect=fake_get), \
             patch.object(config, "DEVICE", "cpu"), \
             patch.object(config, "COMPUTE_TYPE", "int8"), \
             patch.object(config, "AUDIO_CUES", False):
            main._load_settings()
            return config.DEVICE, config.COMPUTE_TYPE, config.AUDIO_CUES

    def test_valid_values_are_applied(self):
        device, compute, cues = self._load_with({
            "device": "cuda",
            "compute_type": "float16",
            "audio_cues": "1",
        })
        self.assertEqual(device, "cuda")
        self.assertEqual(compute, "float16")
        self.assertTrue(cues)

    def test_invalid_device_and_compute_are_ignored(self):
        device, compute, _ = self._load_with({
            "device": "gpu-typo",
            "compute_type": "bogus",
        })
        self.assertEqual(device, "cpu")     # left at default
        self.assertEqual(compute, "int8")   # left at default

    def test_absent_settings_leave_defaults(self):
        device, compute, cues = self._load_with({})
        self.assertEqual(device, "cpu")
        self.assertEqual(compute, "int8")
        self.assertFalse(cues)


if __name__ == "__main__":
    unittest.main()
