"""System tray icon for Writher with Pandora Blackboard eyes."""

import pystray
import locales
from brand import make_tray_icon


class TrayIcon:
    def __init__(self, on_quit, on_show_notes=None):
        self._on_quit = on_quit
        self._on_show_notes = on_show_notes
        self._icon = None

    def _build_menu(self):
        items = [
            pystray.MenuItem("Writher", None, enabled=False),
            pystray.Menu.SEPARATOR,
        ]
        if self._on_show_notes:
            items.append(pystray.MenuItem(locales.get("tray_notes_agenda"), self._show_notes))
            items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem(locales.get("tray_quit"), self._quit))
        return pystray.Menu(*items)

    def _show_notes(self, icon, item):
        if self._on_show_notes:
            self._on_show_notes()

    def _quit(self, icon, item):
        icon.stop()
        self._on_quit()

    def start(self):
        img = make_tray_icon(recording=False)
        self._icon = pystray.Icon(
            "Writher",
            img,
            locales.get("tray_idle"),
            menu=self._build_menu(),
        )
        # run_detached() starts the message loop in an internal thread
        # managed by pystray — the correct non-blocking approach on Windows.
        self._icon.run_detached()

    def set_recording(self, recording: bool):
        if self._icon is None:
            return
        self._icon.icon = make_tray_icon(recording=recording)
        self._icon.title = (locales.get("tray_recording") if recording
                            else locales.get("tray_idle"))

    def set_tooltip(self, text: str):
        """Update the tray icon tooltip text (used for status warnings)."""
        if self._icon is not None:
            self._icon.title = text

    def stop(self):
        if self._icon is not None:
            self._icon.stop()
