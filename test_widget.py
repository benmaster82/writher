import threading
import unittest
from unittest.mock import patch

from widget import RecordingWidget


class _FakeRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))


class WidgetThreadingTests(unittest.TestCase):
    def test_ui_request_from_worker_does_not_call_tk_or_block(self):
        root = _FakeRoot()
        widget = RecordingWidget(root)
        shown = []
        widget._show = shown.append
        root.after_calls.clear()

        worker = threading.Thread(target=widget.show_processing)
        worker.start()
        worker.join(timeout=0.2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(root.after_calls, [])
        self.assertEqual(shown, [])

        widget._drain_ui_queue()

        self.assertEqual(shown, [widget.PROCESSING])
        self.assertEqual(root.after_calls[0][0], 10)

    @patch("widget.log")
    def test_bad_ui_operation_does_not_stop_dispatcher(self, mocked_log):
        root = _FakeRoot()
        widget = RecordingWidget(root)
        completed = []
        root.after_calls.clear()

        def fail():
            raise ValueError("bad update")

        widget._dispatch(fail)
        widget._dispatch(lambda: completed.append(True))
        widget._drain_ui_queue()

        self.assertEqual(completed, [True])
        self.assertEqual(root.after_calls[0][0], 10)
        mocked_log.error.assert_called_once()

    def test_stale_recording_status_is_discarded(self):
        root = _FakeRoot()
        widget = RecordingWidget(root)
        shown = []
        widget._show = shown.append

        widget.show_recording("en", should_show=lambda: False)
        widget._drain_ui_queue()

        self.assertEqual(shown, [])

    def test_immediate_hide_bypasses_fade(self):
        root = _FakeRoot()
        widget = RecordingWidget(root)
        hidden = []
        widget._hide_immediately = lambda: hidden.append(True)

        widget.hide(immediate=True)
        widget._drain_ui_queue()

        self.assertEqual(hidden, [True])
