"""Hotkey serialisation utilities.

Converts pynput Key/KeyCode objects to persistent strings and back,
and provides human-readable display names for the settings UI.
"""

from pynput.keyboard import Key, KeyCode


# ── Serialisation ─────────────────────────────────────────────────────────

def key_to_str(k) -> str:
    """Convert a pynput key object to a storable string."""
    if isinstance(k, Key):
        return f"Key.{k.name}"
    if isinstance(k, KeyCode):
        if k.vk is not None:
            return f"KeyCode({k.vk})"
        if k.char is not None:
            return f"Char({k.char})"
    return str(k)


def str_to_key(s: str):
    """Convert a stored string back to a pynput key object.

    Returns None if the string cannot be parsed.
    """
    if not s:
        return None
    if s.startswith("Key."):
        name = s[4:]
        return getattr(Key, name, None)
    if s.startswith("KeyCode(") and s.endswith(")"):
        try:
            vk = int(s[8:-1])
            return KeyCode.from_vk(vk)
        except (ValueError, TypeError):
            return None
    if s.startswith("Char(") and s.endswith(")"):
        ch = s[5:-1]
        return KeyCode.from_char(ch) if ch else None
    return None


# ── Display names ─────────────────────────────────────────────────────────

_SPECIAL_NAMES: dict[Key, str] = {
    Key.alt_gr:      "AltGr",
    Key.alt_l:       "Alt Left",
    Key.alt_r:       "Alt Right",
    Key.ctrl_l:      "Ctrl Left",
    Key.ctrl_r:      "Ctrl Right",
    Key.shift_l:     "Shift Left",
    Key.shift_r:     "Shift Right",
    Key.space:       "Space",
    Key.enter:       "Enter",
    Key.tab:         "Tab",
    Key.esc:         "Esc",
    Key.backspace:   "Backspace",
    Key.delete:      "Delete",
    Key.insert:      "Insert",
    Key.home:        "Home",
    Key.end:         "End",
    Key.page_up:     "Page Up",
    Key.page_down:   "Page Down",
    Key.caps_lock:   "Caps Lock",
    Key.num_lock:    "Num Lock",
    Key.scroll_lock: "Scroll Lock",
    Key.pause:       "Pause",
    Key.print_screen: "Print Screen",
    Key.menu:        "Menu",
}

# Add F1–F20
for _i in range(1, 21):
    _k = getattr(Key, f"f{_i}", None)
    if _k:
        _SPECIAL_NAMES[_k] = f"F{_i}"


def key_display_name(k) -> str:
    """Return a human-readable name for a key."""
    if isinstance(k, Key):
        return _SPECIAL_NAMES.get(k, k.name.replace("_", " ").title())
    if isinstance(k, KeyCode):
        if k.char and k.char.isprintable():
            return k.char.upper()
        if k.vk is not None:
            return f"Key {k.vk}"
    return str(k)


# ── Blacklist (keys that should not be used as hotkeys) ───────────────────

_BLOCKED_KEYS: set = {
    Key.enter, Key.space, Key.backspace, Key.delete, Key.tab, Key.esc,
    Key.shift_l, Key.shift_r,  # too common as modifiers
}


def is_blocked(k) -> bool:
    """Return True if the key should not be assignable as a hotkey."""
    if isinstance(k, Key):
        return k in _BLOCKED_KEYS
    if isinstance(k, KeyCode):
        # Block regular printable characters (letters, digits)
        if k.char and k.char.isalnum():
            return True
    return False
