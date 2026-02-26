"""Dual-hotkey listener: one for dictation, one for assistant mode.

Supports two recording modes controlled by config.HOLD_TO_RECORD:
  - Hold mode (True):  press=start, release=stop  (original behaviour)
  - Toggle mode (False): press=start, press again=stop  (release ignored)
"""

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
        # Toggle-mode state: True while actively recording
        self._dict_recording = False
        self._assist_recording = False
        self._listener = None

    def _is_hold_mode(self) -> bool:
        return getattr(config, "HOLD_TO_RECORD", True)

    # ── press ─────────────────────────────────────────────────────────────

    def _handle_press(self, key):
        if key == config.HOTKEY:
            if self._is_hold_mode():
                if not self._dict_pressed:
                    self._dict_pressed = True
                    self._safe_call(self._on_press, "Dictation press")
            else:
                # Toggle mode: ignore key-repeat (pressed stays True)
                if self._dict_pressed:
                    return
                self._dict_pressed = True
                if not self._dict_recording:
                    self._dict_recording = True
                    self._safe_call(self._on_press, "Dictation toggle-start")
                else:
                    self._dict_recording = False
                    self._safe_call(self._on_release, "Dictation toggle-stop")

        elif key == config.ASSISTANT_HOTKEY and self._on_assist_press:
            if self._is_hold_mode():
                if not self._assist_pressed:
                    self._assist_pressed = True
                    self._safe_call(self._on_assist_press, "Assistant press")
            else:
                if self._assist_pressed:
                    return
                self._assist_pressed = True
                if not self._assist_recording:
                    self._assist_recording = True
                    self._safe_call(self._on_assist_press, "Assistant toggle-start")
                else:
                    self._assist_recording = False
                    self._safe_call(self._on_assist_release, "Assistant toggle-stop")

    # ── release ───────────────────────────────────────────────────────────

    def _handle_release(self, key):
        if key == config.HOTKEY:
            if self._is_hold_mode():
                if self._dict_pressed:
                    self._dict_pressed = False
                    self._safe_call(self._on_release, "Dictation release")
            else:
                # Toggle mode: just reset the physical-key flag
                self._dict_pressed = False

        elif key == config.ASSISTANT_HOTKEY:
            if self._is_hold_mode():
                if self._assist_pressed and self._on_assist_release:
                    self._assist_pressed = False
                    self._safe_call(self._on_assist_release, "Assistant release")
            else:
                self._assist_pressed = False

    # ── public API to force-stop (used by timeout) ────────────────────────

    def force_stop_dictation(self):
        """Called by the timeout timer to stop a toggle-mode recording."""
        if self._dict_recording:
            self._dict_recording = False
            self._dict_pressed = False
            self._safe_call(self._on_release, "Dictation timeout-stop")

    def force_stop_assistant(self):
        """Called by the timeout timer to stop a toggle-mode recording."""
        if self._assist_recording:
            self._assist_recording = False
            self._assist_pressed = False
            if self._on_assist_release:
                self._safe_call(self._on_assist_release, "Assistant timeout-stop")

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _safe_call(fn, label: str):
        try:
            fn()
        except Exception as exc:
            log.error("%s error: %s", label, exc)

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
