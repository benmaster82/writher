"""Dual-hotkey listener: one for dictation, one for assistant mode.

Supports two recording modes controlled by config.HOLD_TO_RECORD:
  - Hold mode (True):  press=start, release=stop  (original behaviour)
  - Toggle mode (False): press=start, press again=stop  (release ignored)

Toggle mode includes a debounce (300ms) to prevent key-repeat and
accidental double-press from stopping the recording prematurely.

Hotkeys can be a single pynput Key/KeyCode or a combo tuple
(frozenset_of_modifier_strings, trigger_key) — see hotkey_util.py.
"""

import threading
import time
from pynput import keyboard
from pynput.keyboard import Controller, Key, KeyCode
import config
from logger import log
from hotkey_util import canonical_modifier, keys_match

_DEBOUNCE_SEC = 0.3  # minimum time between toggle actions

_DUMMY_VK = 0xE8
_MASK_DELAY_SEC = 0.01
_ALT_KEYS = (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr)


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
        self._kb = Controller()
        self._mask_pending = False
        self._alarm = None
        self._sign = threading.Event()

    def _is_hold_mode(self) -> bool:
        return getattr(config, "HOLD_TO_RECORD", True)

    def _mask_alt_tap(self, key):
        """Schedule a dummy key shortly after an Alt-down event.

        Stops Windows from treating a lone Alt/AltGr press as "open the menu
        bar". Called for EVERY press event, including the auto-repeats sent
        while the key is held, because each repeated Alt-down would otherwise
        re-arm the menu. Only one dummy is queued at a time.
        """
        if key not in _ALT_KEYS or self._mask_pending:
            return
        self._mask_pending = True
        timer = threading.Timer(_MASK_DELAY_SEC, self._send_dummy)
        self._alarm = timer
        self._alarm.daemon = True
        self._alarm.start()

    def _send_dummy(self):
        if not self._sign.is_set():
            return
        try:
            dummy = KeyCode.from_vk(_DUMMY_VK)
            self._kb.press(dummy)
            self._kb.release(dummy)
        except Exception as exc:
            log.error("Alt mask error: %s", exc)
        finally:
            self._mask_pending = False

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

        if (_is_hotkey_match(key, config.HOTKEY, held)
                or _is_hotkey_match(key, config.ASSISTANT_HOTKEY, held)):
            self._mask_alt_tap(key)

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

    def reset_dictation_state(self):
        """Clear dictation press/record flags without firing any callback.

        Used by the hold-mode safety timeout: when a key-release event is lost
        the ``_dict_pressed`` flag stays stuck True, which would silently
        swallow the next press and wedge the hotkey. Resetting it lets the
        hotkey recover after the mic has been force-stopped (issue #25).
        """
        self._dict_pressed = False
        self._dict_recording = False

    def reset_assistant_state(self):
        """Clear assistant press/record flags without firing any callback.

        Hold-mode safety-timeout counterpart to reset_dictation_state()
        (issue #25).
        """
        self._assist_pressed = False
        self._assist_recording = False

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
        self._sign.set()
        self._listener.start()
        self._listener.wait()

    def stop(self):
        self._sign.clear()

        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=1.0)

        if self._alarm is not None:
            self._alarm.cancel()

        self._mask_pending = False
