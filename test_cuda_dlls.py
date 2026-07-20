"""Tests for pip-installed NVIDIA DLL discovery on Windows (issue #21)."""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import transcriber


def _fake_nvidia_tree(root: str) -> None:
    for lib, with_bin in (("cublas", True), ("cudnn", True), ("no_bin", False)):
        lib_dir = os.path.join(root, lib)
        os.makedirs(lib_dir)
        if with_bin:
            os.makedirs(os.path.join(lib_dir, "bin"))


class TestNvidiaBinDirs(unittest.TestCase):
    def test_finds_bin_dirs_of_installed_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            _fake_nvidia_tree(tmp)
            spec = Mock(submodule_search_locations=[tmp])
            with patch.object(transcriber.importlib.util, "find_spec",
                              return_value=spec):
                dirs = transcriber._nvidia_bin_dirs()

        self.assertEqual(
            sorted(dirs),
            sorted([os.path.join(tmp, "cublas", "bin"),
                    os.path.join(tmp, "cudnn", "bin")]),
        )

    def test_no_nvidia_package_returns_empty(self):
        with patch.object(transcriber.importlib.util, "find_spec",
                          return_value=None):
            self.assertEqual(transcriber._nvidia_bin_dirs(), [])


class TestExposeNvidiaDlls(unittest.TestCase):
    def tearDown(self):
        transcriber._dll_dir_handles.clear()

    @patch.object(transcriber.os, "add_dll_directory", create=True)
    def test_adds_each_bin_dir_once(self, add_dll):
        with (
            patch.object(transcriber.sys, "platform", "win32"),
            patch.object(transcriber, "_nvidia_bin_dirs",
                         return_value=["X:\\nv\\cublas\\bin"]),
        ):
            transcriber._expose_nvidia_dlls()
            transcriber._expose_nvidia_dlls()  # idempotent

        add_dll.assert_called_once_with("X:\\nv\\cublas\\bin")
        self.assertEqual(len(transcriber._dll_dir_handles), 1)

    @patch.object(transcriber.os, "add_dll_directory", create=True)
    def test_noop_outside_windows(self, add_dll):
        with patch.object(transcriber.sys, "platform", "linux"):
            transcriber._expose_nvidia_dlls()
        add_dll.assert_not_called()


if __name__ == "__main__":
    unittest.main()
