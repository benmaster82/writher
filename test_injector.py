import unittest
from unittest.mock import call, patch

import config
import injector


class TestInjection(unittest.TestCase):
    @patch.object(injector, "_inject_via_clipboard", return_value=True)
    @patch.object(injector, "_save_recovery")
    def test_saves_recovery_then_uses_clipboard_paste(
            self, save_recovery, clipboard_paste):
        injector.inject("hello")

        save_recovery.assert_called_once_with("hello")
        clipboard_paste.assert_called_once_with("hello")


class TestClipboardPaste(unittest.TestCase):
    def setUp(self):
        self.original_keep = config.KEEP_TRANSCRIPT_IN_CLIPBOARD
        self.original_delay = config.CLIPBOARD_RESTORE_DELAY

    def tearDown(self):
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = self.original_keep
        config.CLIPBOARD_RESTORE_DELAY = self.original_delay

    @patch.object(injector, "_keyboard")
    @patch.object(injector.time, "sleep")
    @patch.object(injector, "_restore_clipboard", return_value=True)
    @patch.object(injector, "_swap_clipboard_for_text",
                  return_value=([(8, 200)], 42))
    def test_restores_all_original_formats_after_paste(
            self, swap, restore, sleep, keyboard):
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = False
        config.CLIPBOARD_RESTORE_DELAY = 0.75

        self.assertTrue(injector._inject_via_clipboard("hello"))

        swap.assert_called_once_with("hello")
        restore.assert_called_once_with([(8, 200)], 42, "hello")
        keyboard.press.assert_called_once_with("v")
        keyboard.release.assert_called_once_with("v")
        self.assertEqual(
            sleep.call_args_list,
            [call(0.05), call(0.75)],
        )

    @patch.object(injector, "_keyboard")
    @patch.object(injector.time, "sleep")
    @patch.object(injector, "_set_clipboard_text", return_value=True)
    def test_retention_leaves_transcript_in_clipboard(
            self, set_clipboard, _sleep, _keyboard):
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = True

        self.assertTrue(injector._inject_via_clipboard("hello"))

        set_clipboard.assert_called_once_with("hello")


class TestClipboardPreservation(unittest.TestCase):
    @patch.object(injector, "_duplicate_clipboard_handle",
                  side_effect=[201, 202])
    @patch.object(injector, "_GetClipboardData", side_effect=[101, 102])
    @patch.object(injector, "_EnumClipboardFormats",
                  side_effect=[injector.CF_UNICODETEXT, 8, 0])
    def test_capture_duplicates_every_enumerated_format(
            self, _enum_formats, _get_data, duplicate):
        snapshot = injector._capture_open_clipboard()

        self.assertEqual(
            snapshot,
            [(injector.CF_UNICODETEXT, 201), (8, 202)],
        )
        self.assertEqual(
            [call.args for call in duplicate.call_args_list],
            [(injector.CF_UNICODETEXT, 101), (8, 102)],
        )

    @patch.object(injector, "_free_clipboard_snapshot")
    @patch.object(injector, "_duplicate_clipboard_handle",
                  side_effect=[201, None])
    @patch.object(injector, "_GetClipboardData", side_effect=[101, 102])
    @patch.object(injector, "_EnumClipboardFormats", side_effect=[13, 8])
    def test_capture_failure_releases_duplicates_without_emptying_clipboard(
            self, _enum_formats, _get_data, _duplicate, free_snapshot):
        self.assertIsNone(injector._capture_open_clipboard())

        free_snapshot.assert_called_once_with([(13, 201)])

    @patch.object(injector, "_CloseClipboard")
    @patch.object(injector, "_GetClipboardSequenceNumber", return_value=77)
    @patch.object(injector, "_SetClipboardData", return_value=300)
    @patch.object(injector, "_EmptyClipboard", return_value=True)
    @patch.object(injector, "_capture_open_clipboard",
                  return_value=[(8, 201)])
    @patch.object(injector, "_open_clipboard", return_value=True)
    @patch.object(injector, "_allocate_clipboard_text", return_value=300)
    def test_swap_backs_up_and_replaces_while_clipboard_stays_open(
            self, _allocate, _open, _capture, empty, set_data,
            _sequence, close):
        self.assertEqual(
            injector._swap_clipboard_for_text("hello"),
            ([(8, 201)], 77),
        )

        empty.assert_called_once_with()
        set_data.assert_called_once_with(injector.CF_UNICODETEXT, 300)
        close.assert_called_once_with()

    @patch.object(injector, "_free_clipboard_snapshot")
    @patch.object(injector, "_CloseClipboard")
    @patch.object(injector, "_EmptyClipboard")
    @patch.object(injector, "_GetClipboardSequenceNumber", return_value=78)
    @patch.object(injector, "_open_clipboard", return_value=True)
    def test_restore_does_not_overwrite_a_new_user_copy(
            self, _open, _sequence, empty, _close, free_snapshot):
        snapshot = [(8, 201), (13, 202)]

        self.assertFalse(injector._restore_clipboard(snapshot, 77))

        empty.assert_not_called()
        free_snapshot.assert_called_once_with(snapshot)

    @patch.object(injector, "_free_clipboard_snapshot")
    @patch.object(injector, "_CloseClipboard")
    @patch.object(injector, "_EmptyClipboard")
    @patch.object(injector, "_open_clipboard_text", return_value="new copy")
    @patch.object(injector, "_GetClipboardSequenceNumber", return_value=77)
    @patch.object(injector, "_open_clipboard", return_value=True)
    def test_restore_checks_temporary_text_as_well_as_sequence(
            self, _open, _sequence, _text, empty, _close, free_snapshot):
        snapshot = [(13, 201)]

        self.assertFalse(
            injector._restore_clipboard(snapshot, 77, "transcript"))

        empty.assert_not_called()
        free_snapshot.assert_called_once_with(snapshot)

    @patch.object(injector, "_free_clipboard_snapshot")
    @patch.object(injector, "_CloseClipboard")
    @patch.object(injector, "_SetClipboardData", return_value=1)
    @patch.object(injector, "_EmptyClipboard", return_value=True)
    @patch.object(injector, "_GetClipboardSequenceNumber", return_value=77)
    @patch.object(injector, "_open_clipboard", return_value=True)
    def test_restore_transfers_every_format_in_original_order(
            self, _open, _sequence, _empty, set_data, _close,
            free_snapshot):
        snapshot = [(8, 201), (13, 202)]

        self.assertTrue(injector._restore_clipboard(snapshot, 77))

        self.assertEqual(
            [call.args for call in set_data.call_args_list],
            [(8, 201), (13, 202)],
        )
        free_snapshot.assert_called_once_with([])

    @patch.object(injector.time, "sleep")
    @patch.object(injector, "_free_clipboard_handle")
    @patch.object(injector, "_free_clipboard_snapshot")
    @patch.object(injector, "_CloseClipboard")
    @patch.object(injector, "_SetClipboardData",
                  side_effect=[1, 0, 0, 0, 1])
    @patch.object(injector, "_EmptyClipboard", return_value=True)
    @patch.object(injector, "_GetClipboardSequenceNumber", return_value=77)
    @patch.object(injector, "_open_clipboard", return_value=True)
    def test_restore_retries_failure_and_continues_with_later_formats(
            self, _open, _sequence, _empty, set_data, _close,
            free_snapshot, free_handle, sleep):
        snapshot = [(8, 201), (9, 202), (13, 203)]

        self.assertFalse(injector._restore_clipboard(snapshot, 77))

        self.assertEqual(
            [item.args for item in set_data.call_args_list],
            [(8, 201), (9, 202), (9, 202), (9, 202), (13, 203)],
        )
        self.assertEqual(sleep.call_count, 2)
        free_handle.assert_called_once_with(9, 202)
        free_snapshot.assert_called_once_with([])


class TestClipboardSnapshotFallback(unittest.TestCase):
    """A failed multi-format snapshot must degrade, not abort the paste."""

    def setUp(self):
        self.original_keep = config.KEEP_TRANSCRIPT_IN_CLIPBOARD
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = False

    def tearDown(self):
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = self.original_keep

    @patch.object(injector, "_keyboard")
    @patch.object(injector.time, "sleep")
    @patch.object(injector, "_restore_text_only", return_value=True)
    @patch.object(injector, "_set_clipboard_text", return_value=True)
    @patch.object(injector, "_get_clipboard_text", return_value="old text")
    @patch.object(injector, "_swap_clipboard_for_text", return_value=None)
    def test_snapshot_failure_falls_back_to_text_only_paste(
            self, swap, get_text, set_text, restore_text, _sleep, keyboard):
        self.assertTrue(injector._inject_via_clipboard("hello"))

        swap.assert_called_once_with("hello")
        get_text.assert_called_once_with()
        set_text.assert_called_once_with("hello")
        keyboard.press.assert_called_once_with("v")
        restore_text.assert_called_once_with("old text", "hello")

    @patch.object(injector, "_keyboard")
    @patch.object(injector, "_restore_text_only")
    @patch.object(injector, "_set_clipboard_text", return_value=False)
    @patch.object(injector, "_get_clipboard_text", return_value="old text")
    @patch.object(injector, "_swap_clipboard_for_text", return_value=None)
    def test_fallback_set_failure_still_aborts_without_restoring(
            self, _swap, _get_text, _set_text, restore_text, keyboard):
        self.assertFalse(injector._inject_via_clipboard("hello"))

        keyboard.press.assert_not_called()
        restore_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
