import unittest
from unittest.mock import Mock, patch

import main


class TestStartupShutdownRace(unittest.TestCase):
    def tearDown(self):
        main._quit_requested.clear()
        main._shutting_down = False
        main.transcriber = None
        main.scheduler = None
        main.hotkey_listener = None

    def test_services_do_not_start_when_quit_arrives_during_model_load(self):
        def finish_model_load():
            main._quit_requested.set()
            return Mock()

        with (
            patch.object(main, "widget", Mock()),
            patch.object(main.db, "get_setting", return_value="1"),
            patch.object(main.db, "save_setting") as save_setting,
            patch.object(main, "Transcriber",
                         side_effect=finish_model_load),
            patch.object(main, "ReminderScheduler") as reminder_scheduler,
            patch.object(main, "HotkeyListener") as hotkey_listener,
        ):
            main._finish_startup()

        save_setting.assert_not_called()
        reminder_scheduler.assert_not_called()
        hotkey_listener.assert_not_called()

    def test_happy_startup_starts_all_services(self):
        """Regression: the full startup path must run without errors.

        A merge once reintroduced a reference to a deleted variable in
        _finish_startup; only the quit-during-load path was tested, so
        the crash surfaced at runtime."""
        with (
            patch.object(main, "widget", Mock()),
            patch.object(main.db, "get_setting", return_value="1"),
            patch.object(main.db, "save_setting"),
            patch.object(main, "Transcriber", return_value=Mock()),
            patch.object(main, "ReminderScheduler") as scheduler_cls,
            patch.object(main, "HotkeyListener") as listener_cls,
            patch.object(main.threading, "Thread") as thread_cls,
            patch.object(main.notifier, "notify") as notify,
        ):
            main._finish_startup()

        scheduler_cls.return_value.start.assert_called_once_with()
        listener_cls.return_value.start.assert_called_once_with()
        self.assertEqual(thread_cls.call_count, 2)  # pipeline workers
        notify.assert_not_called()  # welcome toast already shown


if __name__ == "__main__":
    unittest.main()
