"""Runtime configurability of compute device / precision (issue #23).

DEVICE and COMPUTE_TYPE are selectable from Settings and persisted, so packaged
users can enable CUDA without editing config.py. The Settings callbacks are
exercised on a bare SettingsWindow shell (no Tk); the startup load path is
exercised through main._load_settings.

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


class TestLoadSettings(unittest.TestCase):
    """main._load_settings applies persisted device/compute to config."""

    def _load_with(self, values):
        def fake_get(key, default=""):
            return values.get(key, "")
        with patch.object(main.db, "get_setting", side_effect=fake_get), \
             patch.object(config, "DEVICE", "cpu"), \
             patch.object(config, "COMPUTE_TYPE", "int8"):
            main._load_settings()
            return config.DEVICE, config.COMPUTE_TYPE

    def test_valid_values_are_applied(self):
        device, compute = self._load_with({
            "device": "cuda",
            "compute_type": "float16",
        })
        self.assertEqual(device, "cuda")
        self.assertEqual(compute, "float16")

    def test_invalid_device_and_compute_are_ignored(self):
        device, compute = self._load_with({
            "device": "gpu-typo",
            "compute_type": "bogus",
        })
        self.assertEqual(device, "cpu")     # left at default
        self.assertEqual(compute, "int8")   # left at default

    def test_absent_settings_leave_defaults(self):
        device, compute = self._load_with({})
        self.assertEqual(device, "cpu")
        self.assertEqual(compute, "int8")


if __name__ == "__main__":
    unittest.main()
