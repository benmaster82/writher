"""Voice-delete confirmation now uses the floating agent panel (main.py).

The confirmation moved from a separate Notes-window popup into the dedicated
AgentPanel: _set_pending_delete shows the rich confirm card with a live
countdown, and the panel calls _on_confirm_timeout when it elapses unanswered.

Run:  python -m unittest test_inline_confirm -v
"""

import unittest
from unittest.mock import Mock, patch

import config
import main


class TestInlineConfirm(unittest.TestCase):
    def setUp(self):
        main._pending_delete = None

    def tearDown(self):
        main._pending_delete = None

    def test_set_pending_delete_shows_panel_and_hides_pill(self):
        panel, pill = Mock(), Mock()
        with patch.object(main, "agent_panel", panel), \
             patch.object(main, "widget", pill), \
             patch.object(config, "LANGUAGE", "en"):
            main._set_pending_delete("note", 7)

        self.assertEqual(main._pending_delete["kind"], "note")
        self.assertEqual(main._pending_delete["id"], 7)
        pill.hide.assert_called_once()          # pill dismissed
        panel.show_confirm.assert_called_once()
        args, kwargs = panel.show_confirm.call_args
        self.assertEqual(args[0], "Delete note?")   # localized, no seconds baked in
        self.assertEqual(args[1], main._DELETE_CONFIRM_SECONDS)
        self.assertIs(kwargs["on_timeout"], main._on_confirm_timeout)

    def test_set_pending_delete_does_not_open_notes_popup(self):
        notes = Mock()
        with patch.object(main, "agent_panel", Mock()), \
             patch.object(main, "widget", Mock()), \
             patch.object(main, "notes_win", notes):
            main._set_pending_delete("appointment", 3)
        notes.show_voice_delete_confirmation.assert_not_called()

    def test_timeout_clears_pending_hides_panel_and_notifies(self):
        panel, pill = Mock(), Mock()
        main._pending_delete = {"kind": "note", "id": 7, "expires_at": 0.0}
        with patch.object(main, "agent_panel", panel), \
             patch.object(main, "widget", pill), \
             patch.object(config, "LANGUAGE", "en"):
            main._on_confirm_timeout()

        self.assertIsNone(main._pending_delete)
        panel.hide.assert_called_once()
        pill.set_expression.assert_called_with("sad")
        pill.show_message.assert_called_once()

    def test_timeout_is_noop_when_nothing_pending(self):
        panel = Mock()
        main._pending_delete = None
        with patch.object(main, "agent_panel", panel), patch.object(main, "widget", Mock()):
            main._on_confirm_timeout()
        panel.hide.assert_not_called()

    def test_set_pending_delete_starts_autolisten_when_ready(self):
        with patch.object(main, "agent_panel", Mock()), \
             patch.object(main, "widget", Mock()), \
             patch.object(main, "transcriber", Mock()), \
             patch.object(main.threading, "Thread") as thread:
            main._set_pending_delete("note", 1)
        thread.assert_called_once()
        self.assertIs(thread.call_args.kwargs["target"], main._confirm_listen)
        thread.return_value.start.assert_called_once_with()

    def test_set_pending_delete_skips_autolisten_without_transcriber(self):
        with patch.object(main, "agent_panel", Mock()), \
             patch.object(main, "widget", Mock()), \
             patch.object(main, "transcriber", None), \
             patch.object(main.threading, "Thread") as thread:
            main._set_pending_delete("note", 1)
        thread.assert_not_called()


class TestApplyConfirmResult(unittest.TestCase):
    def test_success_shows_check_and_hides_panel(self):
        panel, pill = Mock(), Mock()
        with patch.object(main, "agent_panel", panel), patch.object(main, "widget", pill):
            main._apply_confirm_result("Nota 'x' eliminata (#7)")
        panel.hide.assert_called_once()
        pill.set_expression.assert_called_with("happy")
        pill.show_message.assert_called_once()

    def test_cancelled_shows_sad(self):
        panel, pill = Mock(), Mock()
        with patch.object(main, "agent_panel", panel), patch.object(main, "widget", pill), \
             patch.object(config, "LANGUAGE", "en"):
            main._apply_confirm_result("__delete_cancelled__")
        panel.hide.assert_called_once()
        pill.set_expression.assert_called_with("sad")

    def test_timeout_token_shows_sad(self):
        panel, pill = Mock(), Mock()
        with patch.object(main, "agent_panel", panel), patch.object(main, "widget", pill), \
             patch.object(config, "LANGUAGE", "en"):
            main._apply_confirm_result("__delete_confirm_timeout__")
        pill.set_expression.assert_called_with("sad")


if __name__ == "__main__":
    unittest.main()
