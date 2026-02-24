"""Dual-hotkey listener: one for dictation, one for assistant mode."""

from pynput import keyboard
import config
from logger import log


class HotkeyListener:
    def __init__(self, on_press_cb, on_release_cb,
                 on_assist_press_cb=None, on_assist_release_cb=None):
        self._on_press = on_press_cb
        self._on_release = on_release_cb
        self._on_assist_press = on_assist_press_cb
        self._on_assist_release = on_assist_release_cb
        self._dict_pressed = False
        self._assist_pressed = False
        self._listener = None

    def _handle_press(self, key):
        if key == config.HOTKEY and not self._dict_pressed:
            self._dict_pressed = True
            try:
                self._on_press()
            except Exception as exc:
                log.error("Dictation press error: %s", exc)

        elif (key == config.ASSISTANT_HOTKEY
              and self._on_assist_press
              and not self._assist_pressed):
            self._assist_pressed = True
            try:
                self._on_assist_press()
            except Exception as exc:
                log.error("Assistant press error: %s", exc)

    def _handle_release(self, key):
        if key == config.HOTKEY and self._dict_pressed:
            self._dict_pressed = False
            try:
                self._on_release()
            except Exception as exc:
                log.error("Dictation release error: %s", exc)

        elif (key == config.ASSISTANT_HOTKEY
              and self._on_assist_release
              and self._assist_pressed):
            self._assist_pressed = False
            try:
                self._on_assist_release()
            except Exception as exc:
                log.error("Assistant release error: %s", exc)

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()
        self._listener.wait()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
