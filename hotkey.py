"""Dual-hotkey listener: one for dictation, one for assistant mode.

Supports two recording modes controlled by config.HOLD_TO_RECORD:
  - Hold mode (True):  press=start, release=stop  (original behaviour)
  - Toggle mode (False): press=start, press again=stop  (release ignored)

Toggle mode includes a debounce (300ms) to prevent key-repeat and
accidental double-press from stopping the recording prematurely.

Hotkeys can be a single pynput Key/KeyCode or a combo tuple
(frozenset_of_modifier_strings, trigger_key) — see hotkey_util.py.
"""

import time
from pynput import keyboard
import config
from logger import log
from hotkey_util import canonical_modifier, keys_match

_DEBOUNCE_SEC = 0.3  # minimum time between toggle actions


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


def _is_bare_modifier_hotkey(key, hotkey) -> bool:
    """Return True if *hotkey* is configured as exactly this modifier key.

    Lets users bind a bare modifier (e.g. ``Key.ctrl_r`` in config.py) as a
    hotkey instead of it being silently swallowed by modifier tracking.
    """
    return not isinstance(hotkey, tuple) and keys_match(key, hotkey)


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

    def _is_hold_mode(self) -> bool:
        return getattr(config, "HOLD_TO_RECORD", True)

    # ── press ─────────────────────────────────────────────────────────────

    def _handle_press(self, key):
        # Track modifier state first. A modifier key normally never starts
        # recording, except when this exact key is itself a configured
        # hotkey (e.g. HOTKEY = Key.ctrl_r) — see issue #19.
        mod = canonical_modifier(key)
        if mod is not None:
            self._held_modifiers.add(mod)
            if not (_is_bare_modifier_hotkey(key, config.HOTKEY)
                    or _is_bare_modifier_hotkey(key, config.ASSISTANT_HOTKEY)):
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

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _safe_call(fn, label: str):
        try:
            fn()
        except Exception as exc:
            log.error("%s error: %s", label, exc)

    def _warn_bare_modifier_conflicts(self):
        """Log configured bare-modifier hotkeys and any combo overlap."""
        pairs = (
            (config.HOTKEY, config.ASSISTANT_HOTKEY, "Dictation"),
            (config.ASSISTANT_HOTKEY, config.HOTKEY, "Assistant"),
        )
        for own, other, label in pairs:
            if isinstance(own, tuple):
                continue
            mod = canonical_modifier(own)
            if mod is None:
                continue
            log.info("%s hotkey is a bare modifier key: %s", label, own)
            if isinstance(other, tuple) and mod in other[0]:
                log.warning(
                    "Hotkey conflict: %s hotkey %s is also a '%s' modifier "
                    "of the other combo hotkey %s — holding it will start "
                    "recording before the combo completes.",
                    label, own, mod, other)

    def start(self):
        self._warn_bare_modifier_conflicts()
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()
        self._listener.wait()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=1.0)
