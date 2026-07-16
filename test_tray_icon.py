import threading
import unittest
from unittest.mock import patch

import tray_icon


class TestTrayShutdown(unittest.TestCase):
    @patch.object(tray_icon, "make_tray_icon")
    @patch.object(tray_icon.pystray, "Icon")
    def test_stop_joins_the_daemon_tray_thread(self, icon_class, _image):
        release = threading.Event()
        native_icon = icon_class.return_value
        native_icon.run.side_effect = release.wait
        native_icon.stop.side_effect = release.set
        tray = tray_icon.TrayIcon(on_quit=lambda: None)

        tray.start()
        self.assertTrue(tray._thread.daemon)

        tray.stop()

        native_icon.stop.assert_called_once_with()
        self.assertFalse(tray._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
