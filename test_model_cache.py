"""Tests for the Whisper model cache detection (issue #16 stuck-loading fix).

An interrupted first download leaves *.incomplete blobs and a snapshot
without model.bin; that must be treated as NOT cached so startup honestly
says "Downloading" and does not attempt a no-network load.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import main


def _make_cache(root: str, size: str = "small", with_weights: bool = True,
                incomplete_blob: bool = False) -> None:
    model_dir = os.path.join(root, f"models--Systran--faster-whisper-{size}")
    snap = os.path.join(model_dir, "snapshots", "abc123")
    blobs = os.path.join(model_dir, "blobs")
    os.makedirs(snap)
    os.makedirs(blobs)
    if with_weights:
        open(os.path.join(snap, "model.bin"), "wb").write(b"x")
    if incomplete_blob:
        open(os.path.join(blobs, "deadbeef.incomplete"), "wb").write(b"x")


class TestWhisperModelCacheDetection(unittest.TestCase):
    def _check(self, **kwargs) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            _make_cache(tmp, **kwargs)
            with patch.dict(os.environ, {"HF_HUB_CACHE": tmp}):
                return main._whisper_model_is_cached("small")

    def test_complete_cache_is_detected(self):
        self.assertTrue(self._check())

    def test_incomplete_blob_means_not_cached(self):
        self.assertFalse(self._check(incomplete_blob=True))

    def test_snapshot_without_weights_means_not_cached(self):
        self.assertFalse(self._check(with_weights=False))

    def test_missing_model_dir_means_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HF_HUB_CACHE": tmp}):
                self.assertFalse(main._whisper_model_is_cached("small"))


if __name__ == "__main__":
    unittest.main()
