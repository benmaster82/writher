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


if __name__ == "__main__":
    unittest.main()
