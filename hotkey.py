"""Dual-hotkey listener: one for dictation, one for assistant mode.

Supports two recording modes controlled by config.HOLD_TO_RECORD:
  - Hold mode (True):  press=start, release=stop  (original behaviour)
  - Toggle mode (False): press=start, press again=stop  (release ignored)

Toggle mode includes a debounce (300ms) to prevent key-repeat and
accidental double-press from stopping the recording prematurely.

Hotkeys can be a single pynput Key/KeyCode or a combo tuple
(frozenset_of_modifier_strings, trigger_key) — see hotkey_util.py.
"""

import queue
import threading
import time
from pynput import keyboard
import config
from logger import log
from hotkey_util import canonical_modifier, keys_match

_DEBOUNCE_SEC = 0.3  # minimum time between toggle actions
_STOP_CALLBACKS = object()


# ── Hotkey matching helpers ───────────────────────────────────────────────

def _is_hotkey_match(key, hotkey, held_mods: frozenset) -> bool:
    """Return True if key+held_mods satisfies the configured hotkey.

    Single-key hotkeys match regardless of held modifiers (backward compat).
    Combo hotkeys require an exact modifier set match.
    """
    if isinstance(hotkey, tuple):
        required_mods, trigger = hotkey
        return required_mods == held_mods and keys_match(key, trigger)
    return keys_match(key, hotkey)


def _is_trigger_match(key, hotkey) -> bool:
    """Return True if key matches the trigger part of a hotkey.

    Used on key-release to fire the stop callback without re-checking modifiers.
    """
    if isinstance(hotkey, tuple):
        _, trigger = hotkey
        return keys_match(key, trigger)
    return keys_match(key, hotkey)


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
        # Debounce timestamps (toggle mode only)
        self._dict_last_toggle = 0.0
        self._assist_last_toggle = 0.0
        # Currently held modifier keys (canonical names: "ctrl", "shift", etc.)
        self._held_modifiers: set = set()
        self._listener = None
        # pynput invokes handlers on its event thread.  Microphone startup can
        # block there, which prevents a physical key release from being seen.
        # Preserve callback order on a separate worker while keeping pynput's
        # event thread responsive.
        self._callback_queue = queue.Queue()
        self._callback_stopped = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._callback_worker = threading.Thread(
            target=self._run_callbacks, daemon=True)
        self._callback_worker.start()

    def _is_hold_mode(self) -> bool:
        return getattr(config, "HOLD_TO_RECORD", True)

    # ── press ─────────────────────────────────────────────────────────────

    def _handle_press(self, key):
        # Track modifier state first; modifiers alone never start recording.
        mod = canonical_modifier(key)
        if mod is not None:
            self._held_modifiers.add(mod)
            return

        held = frozenset(self._held_modifiers)

        if _is_hotkey_match(key, config.HOTKEY, held):
            if self._is_hold_mode():
                if not self._dict_pressed:
                    self._dict_pressed = True
                    self._safe_call(self._on_press, "Dictation press")
            else:
                now = time.monotonic()
                if now - self._dict_last_toggle < _DEBOUNCE_SEC:
                    return
                self._dict_last_toggle = now
                if not self._dict_recording:
                    self._dict_recording = True
                    self._safe_call(self._on_press, "Dictation toggle-start")
                else:
                    self._dict_recording = False
                    self._safe_call(self._on_release, "Dictation toggle-stop")

        elif _is_hotkey_match(key, config.ASSISTANT_HOTKEY, held) and self._on_assist_press:
            if self._is_hold_mode():
                if not self._assist_pressed:
                    self._assist_pressed = True
                    self._safe_call(self._on_assist_press, "Assistant press")
            else:
                now = time.monotonic()
                if now - self._assist_last_toggle < _DEBOUNCE_SEC:
                    return
                self._assist_last_toggle = now
                if not self._assist_recording:
                    self._assist_recording = True
                    self._safe_call(self._on_assist_press, "Assistant toggle-start")
                else:
                    self._assist_recording = False
                    self._safe_call(self._on_assist_release, "Assistant toggle-stop")

    # ── release ───────────────────────────────────────────────────────────

    def _handle_release(self, key):
        # Check trigger release before updating modifier state.
        if _is_trigger_match(key, config.HOTKEY):
            if self._is_hold_mode():
                if self._dict_pressed:
                    self._dict_pressed = False
                    self._safe_call(self._on_release, "Dictation release")
            else:
                self._dict_pressed = False

        elif _is_trigger_match(key, config.ASSISTANT_HOTKEY):
            if self._is_hold_mode():
                if self._assist_pressed and self._on_assist_release:
                    self._assist_pressed = False
                    self._safe_call(self._on_assist_release, "Assistant release")
            else:
                self._assist_pressed = False

        # Update modifier tracking after checking release.
        mod = canonical_modifier(key)
        if mod is not None:
            self._held_modifiers.discard(mod)

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

    def cancel_dictation_start(self):
        """Reset dictation key state after microphone startup fails."""
        self._dict_recording = False
        self._dict_pressed = False

    def cancel_assistant_start(self):
        """Reset assistant key state after microphone startup fails."""
        self._assist_recording = False
        self._assist_pressed = False

    # ── helpers ───────────────────────────────────────────────────────────

    def _safe_call(self, fn, label: str):
        if not self._callback_stopped.is_set():
            self._callback_queue.put((fn, label))

    def _run_callbacks(self):
        while True:
            item = self._callback_queue.get()
            if item is _STOP_CALLBACKS:
                return
            if self._callback_stopped.is_set():
                continue
            fn, label = item
            try:
                fn()
            except Exception as exc:
                log.error("%s error: %s", label, exc)

    def start(self):
        with self._lifecycle_lock:
            if self._callback_stopped.is_set():
                return
            self._listener = keyboard.Listener(
                on_press=self._handle_press,
                on_release=self._handle_release,
            )
            self._listener.start()
        self._listener.wait()

    def stop(self):
        self._callback_stopped.set()
        with self._lifecycle_lock:
            if self._listener is not None:
                self._listener.stop()
        self._callback_queue.put(_STOP_CALLBACKS)
        if threading.current_thread() is not self._callback_worker:
            self._callback_worker.join()
