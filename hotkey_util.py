"""Hotkey serialisation utilities.

Converts pynput Key/KeyCode objects to persistent strings and back,
and provides human-readable display names for the settings UI.

Hotkeys can be:
  - A single pynput Key or KeyCode (e.g. Key.alt_gr, Key.f9)
  - A combo tuple: (frozenset_of_modifier_strings, trigger_key)
    e.g. (frozenset({"ctrl", "shift"}), KeyCode.from_vk(82)) for Ctrl+Shift+R
"""

from pynput.keyboard import Key, KeyCode


# ── Modifier classification ───────────────────────────────────────────────

# Key.alt_gr is intentionally absent — it acts as a trigger key, not a modifier.
_MODIFIER_MAP: dict = {
    Key.ctrl:    "ctrl",  Key.ctrl_l:  "ctrl",  Key.ctrl_r:  "ctrl",
    Key.shift:   "shift", Key.shift_l: "shift",  Key.shift_r: "shift",
    Key.alt:     "alt",   Key.alt_l:   "alt",    Key.alt_r:   "alt",
    Key.cmd:     "win",   Key.cmd_l:   "win",    Key.cmd_r:   "win",
}


def canonical_modifier(key) -> "str | None":
    """Return canonical modifier name ("ctrl"/"shift"/"alt"/"win") or None."""
    return _MODIFIER_MAP.get(key)


# ── Key equality ──────────────────────────────────────────────────────────

def keys_match(a, b) -> bool:
    """Compare two single pynput keys, normalising KeyCode by VK code."""
    if a == b:
        return True
    if isinstance(a, KeyCode) and isinstance(b, KeyCode):
        if a.vk is not None and b.vk is not None:
            return a.vk == b.vk
    return False


def hotkeys_equal(a, b) -> bool:
    """Compare two hotkeys (single key or combo tuple) for equality."""
    if isinstance(a, tuple) and isinstance(b, tuple):
        return a[0] == b[0] and keys_match(a[1], b[1])
    if isinstance(a, tuple) or isinstance(b, tuple):
        return False
    return keys_match(a, b)


# ── Serialisation ─────────────────────────────────────────────────────────

def _single_key_to_str(k) -> str:
    if isinstance(k, Key):
        return f"Key.{k.name}"
    if isinstance(k, KeyCode):
        if k.vk is not None:
            return f"KeyCode({k.vk})"
        if k.char is not None:
            return f"Char({k.char})"
    return str(k)


def key_to_str(k) -> str:
    """Convert a hotkey (single key or combo tuple) to a storable string."""
    if isinstance(k, tuple):
        mods, trigger = k
        mod_str = "+".join(sorted(mods))
        return f"Combo:{mod_str}:{_single_key_to_str(trigger)}"
    return _single_key_to_str(k)


def _parse_single_key(s: str):
    if not s:
        return None
    if s.startswith("Key."):
        return getattr(Key, s[4:], None)
    if s.startswith("KeyCode(") and s.endswith(")"):
        try:
            return KeyCode.from_vk(int(s[8:-1]))
        except (ValueError, TypeError):
            return None
    if s.startswith("Char(") and s.endswith(")"):
        ch = s[5:-1]
        return KeyCode.from_char(ch) if ch else None
    return None


def str_to_key(s: str):
    """Convert a stored string back to a hotkey (single key or combo tuple).

    Returns None if the string cannot be parsed.
    """
    if not s:
        return None
    if s.startswith("Combo:"):
        rest = s[6:]
        colon_idx = rest.rfind(":")
        if colon_idx < 0:
            return None
        mod_str, key_str = rest[:colon_idx], rest[colon_idx + 1:]
        mods = frozenset(m for m in mod_str.split("+") if m)
        trigger = _parse_single_key(key_str)
        if trigger is None:
            return None
        return (mods, trigger)
    return _parse_single_key(s)


# ── Display names ─────────────────────────────────────────────────────────

_SPECIAL_NAMES: dict = {
    Key.alt_gr:       "AltGr",
    Key.alt_l:        "Alt Left",
    Key.alt_r:        "Alt Right",
    Key.ctrl_l:       "Ctrl Left",
    Key.ctrl_r:       "Ctrl Right",
    Key.shift_l:      "Shift Left",
    Key.shift_r:      "Shift Right",
    Key.space:        "Space",
    Key.enter:        "Enter",
    Key.tab:          "Tab",
    Key.esc:          "Esc",
    Key.backspace:    "Backspace",
    Key.delete:       "Delete",
    Key.insert:       "Insert",
    Key.home:         "Home",
    Key.end:          "End",
    Key.page_up:      "Page Up",
    Key.page_down:    "Page Down",
    Key.caps_lock:    "Caps Lock",
    Key.num_lock:     "Num Lock",
    Key.scroll_lock:  "Scroll Lock",
    Key.pause:        "Pause",
    Key.print_screen: "Print Screen",
    Key.menu:         "Menu",
}

for _i in range(1, 21):
    _k = getattr(Key, f"f{_i}", None)
    if _k:
        _SPECIAL_NAMES[_k] = f"F{_i}"

_MOD_DISPLAY = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win"}
_MOD_ORDER   = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}


def _trigger_display(k) -> str:
    """Human-readable name for a single trigger key."""
    if isinstance(k, Key):
        return _SPECIAL_NAMES.get(k, k.name.replace("_", " ").title())
    if isinstance(k, KeyCode):
        if k.char and k.char.isprintable():
            return k.char.upper()
        if k.vk is not None:
            if 65 <= k.vk <= 90:
                return chr(k.vk)   # A-Z
            if 48 <= k.vk <= 57:
                return chr(k.vk)   # 0-9
            return f"Key {k.vk}"
    return str(k)


def key_display_name(k) -> str:
    """Return a human-readable name for a hotkey (single key or combo tuple)."""
    if isinstance(k, tuple):
        mods, trigger = k
        sorted_mods = sorted(mods, key=lambda m: _MOD_ORDER.get(m, 99))
        parts = [_MOD_DISPLAY.get(m, m.title()) for m in sorted_mods]
        parts.append(_trigger_display(trigger))
        return "+".join(parts)
    return _trigger_display(k)


# ── Blacklist (keys that should not be used as hotkeys) ───────────────────

_BLOCKED_KEYS: set = {
    Key.enter, Key.space, Key.backspace, Key.delete, Key.tab, Key.esc,
    Key.shift_l, Key.shift_r,
}


def is_blocked(k) -> bool:
    """Return True if the key should not be assignable as a hotkey."""
    if isinstance(k, tuple):
        return False  # combos are always allowed
    if isinstance(k, Key):
        return k in _BLOCKED_KEYS
    if isinstance(k, KeyCode):
        if k.char and k.char.isalnum():
            return True
    return False
