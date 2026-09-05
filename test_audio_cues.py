"""Audio-cue generation and playback tests (issue #24).

The winsound backend is mocked: it is Windows-only and would make noise. These
tests pin that the tones are valid WAV, that playback uses SND_MEMORY, that a
failing backend never propagates, and that start/stop use distinct pitches.

Run:  python -m unittest test_audio_cues -v
"""

import io
import sys
import unittest
import wave
from unittest.mock import Mock, patch

import audio_cues


class TestToneRendering(unittest.TestCase):
    def setUp(self):
        audio_cues._cache.clear()

    def test_render_produces_readable_mono_16bit_wav(self):
        data = audio_cues._render_tone(audio_cues._START_FREQ)
        with wave.open(io.BytesIO(data), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getframerate(), audio_cues._SAMPLE_RATE)
            self.assertGreater(w.getnframes(), 0)

    def test_render_is_cached(self):
        first = audio_cues._render_tone(audio_cues._STOP_FREQ)
        second = audio_cues._render_tone(audio_cues._STOP_FREQ)
        self.assertIs(first, second)


class TestPlayback(unittest.TestCase):
    @staticmethod
    def _fake_winsound():
        ws = Mock()
        ws.SND_MEMORY = 4
        ws.SND_ASYNC = 1
        return ws

    def test_play_uses_snd_memory_without_async(self):
        ws = self._fake_winsound()
        with patch.dict(sys.modules, {"winsound": ws}):
            audio_cues._play(audio_cues._START_FREQ)
        ws.PlaySound.assert_called_once()
        args, _ = ws.PlaySound.call_args
        self.assertIsInstance(args[0], (bytes, bytearray))
        # SND_MEMORY must be set; SND_ASYNC must NOT — combining them raises
        # "Cannot play asynchronously from memory" in real winsound.
        self.assertTrue(args[1] & ws.SND_MEMORY)
        self.assertFalse(args[1] & ws.SND_ASYNC)

    def test_play_swallows_backend_errors(self):
        ws = self._fake_winsound()
        ws.PlaySound.side_effect = RuntimeError("no audio device")
        with patch.dict(sys.modules, {"winsound": ws}):
            audio_cues._play(audio_cues._STOP_FREQ)  # must not raise

    def test_play_async_is_noop_off_windows(self):
        with patch.object(audio_cues.sys, "platform", "linux"), \
             patch.object(audio_cues.threading, "Thread") as thread:
            audio_cues._play_async(audio_cues._START_FREQ)
        thread.assert_not_called()

    def test_play_async_spawns_daemon_thread_on_windows(self):
        with patch.object(audio_cues.sys, "platform", "win32"), \
             patch.object(audio_cues.threading, "Thread") as thread:
            audio_cues._play_async(audio_cues._START_FREQ)
        thread.assert_called_once()
        self.assertTrue(thread.call_args.kwargs.get("daemon"))
        thread.return_value.start.assert_called_once_with()

    def test_start_is_higher_pitch_than_stop(self):
        with patch.object(audio_cues, "_play_async") as play:
            audio_cues.play_start()
            audio_cues.play_stop()
        freqs = [c.args[0] for c in play.call_args_list]
        self.assertEqual(
            freqs, [audio_cues._START_FREQ, audio_cues._STOP_FREQ])
        self.assertGreater(audio_cues._START_FREQ, audio_cues._STOP_FREQ)


if __name__ == "__main__":
    unittest.main()
