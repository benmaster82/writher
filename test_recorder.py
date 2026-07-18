import unittest
from unittest.mock import MagicMock, patch

import numpy as np

import config
from recorder import Recorder, _resolve_device


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.original_device = config.MIC_DEVICE_NAME
        config.MIC_DEVICE_NAME = None

    def tearDown(self):
        config.MIC_DEVICE_NAME = self.original_device

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_reuses_stopped_stream_between_recordings(
            self, input_stream, _resolve):
        stream = MagicMock()
        stream.active = False
        input_stream.return_value = stream
        recorder = Recorder()

        self.assertTrue(recorder.prepare())
        recorder.start()
        recorder.stop()
        recorder.start()
        recorder.stop()

        input_stream.assert_called_once()
        self.assertEqual(stream.start.call_count, 2)
        self.assertEqual(stream.stop.call_count, 2)
        stream.close.assert_not_called()

        recorder.close()
        stream.close.assert_called_once()

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_reopens_stream_after_microphone_setting_changes(
            self, input_stream, _resolve):
        first, second = MagicMock(), MagicMock()
        first.active = False
        second.active = False
        input_stream.side_effect = [first, second]
        recorder = Recorder()

        self.assertTrue(recorder.prepare())
        config.MIC_DEVICE_NAME = "New microphone"
        recorder.start()

        self.assertEqual(input_stream.call_count, 2)
        first.close.assert_called_once()
        second.start.assert_called_once()

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_prepare_leaves_stream_stopped(self, input_stream, _resolve):
        stream = MagicMock()
        stream.active = False
        input_stream.return_value = stream
        recorder = Recorder()

        self.assertTrue(recorder.prepare())

        stream.start.assert_not_called()

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_stop_returns_audio_without_closing_stream(
            self, input_stream, _resolve):
        stream = MagicMock()
        stream.active = False
        input_stream.return_value = stream
        recorder = Recorder()
        recorder.start()
        recorder._frames = [
            np.array([[0.1], [0.2]], dtype=np.float32),
            np.array([[0.3]], dtype=np.float32),
        ]

        audio = recorder.stop()

        np.testing.assert_allclose(audio, [0.1, 0.2, 0.3])
        stream.stop.assert_called_once()
        stream.close.assert_not_called()

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_first_audio_notifies_started_callback(
            self, input_stream, _resolve):
        stream = MagicMock()
        stream.active = False
        input_stream.return_value = stream
        recorder = Recorder()
        recorder.on_started = MagicMock()
        recorder.start()

        recorder._callback(
            np.array([[0.1]], dtype=np.float32), 1, None, None)
        recorder._callback(
            np.array([[0.2]], dtype=np.float32), 1, None, None)

        recorder.on_started.assert_called_once()

    @patch("recorder._resolve_device", return_value=None)
    @patch("recorder.sd.InputStream")
    def test_first_audio_is_saved_before_started_callback(
            self, input_stream, _resolve):
        stream = MagicMock()
        stream.active = False
        input_stream.return_value = stream
        recorder = Recorder()
        frame_counts = []
        recorder.on_started = lambda: frame_counts.append(len(recorder._frames))
        recorder.start()

        recorder._callback(
            np.array([[0.1]], dtype=np.float32), 1, None, None)

        self.assertEqual(frame_counts, [1])


class ResolveDeviceTests(unittest.TestCase):
    def test_system_default_uses_portaudio_default(self):
        self.assertIsNone(_resolve_device(None))


if __name__ == "__main__":
    unittest.main()
