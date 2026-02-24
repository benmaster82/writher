"""Inject transcribed text into the active application using the clipboard.

Uses the Win32 clipboard API (via ctypes) for atomic clipboard access,
eliminating the race condition that existed with pyperclip.
If clipboard injection fails, text is saved to recovery_notes.txt as fallback.
"""

import ctypes
import ctypes.wintypes
import os
import time

from pynput.keyboard import Controller, Key
from logger import log

_RECOVERY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovery_notes.txt")

_keyboard = Controller()

# ── Win32 clipboard constants & functions ─────────────────────────────────
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13

_OpenClipboard = _user32.OpenClipboard
_OpenClipboard.argtypes = [ctypes.wintypes.HWND]
_OpenClipboard.restype = ctypes.wintypes.BOOL

_CloseClipboard = _user32.CloseClipboard
_CloseClipboard.argtypes = []
_CloseClipboard.restype = ctypes.wintypes.BOOL

_EmptyClipboard = _user32.EmptyClipboard
_EmptyClipboard.argtypes = []
_EmptyClipboard.restype = ctypes.wintypes.BOOL

_SetClipboardData = _user32.SetClipboardData
_SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.wintypes.HANDLE]
_SetClipboardData.restype = ctypes.wintypes.HANDLE

_GetClipboardData = _user32.GetClipboardData
_GetClipboardData.argtypes = [ctypes.wintypes.UINT]
_GetClipboardData.restype = ctypes.wintypes.HANDLE

_GlobalAlloc = _kernel32.GlobalAlloc
_GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
_GlobalAlloc.restype = ctypes.wintypes.HANDLE

_GlobalLock = _kernel32.GlobalLock
_GlobalLock.argtypes = [ctypes.wintypes.HANDLE]
_GlobalLock.restype = ctypes.c_void_p

_GlobalUnlock = _kernel32.GlobalUnlock
_GlobalUnlock.argtypes = [ctypes.wintypes.HANDLE]
_GlobalUnlock.restype = ctypes.wintypes.BOOL

GMEM_MOVEABLE = 0x0002

_MAX_RETRIES = 5
_RETRY_DELAY = 0.02  # seconds


# ── Clipboard helpers ─────────────────────────────────────────────────────

def _open_clipboard() -> bool:
    """Try to open the clipboard with retries (another app may hold it)."""
    for _ in range(_MAX_RETRIES):
        if _OpenClipboard(None):
            return True
        time.sleep(_RETRY_DELAY)
    return False


def _get_clipboard_text() -> str:
    """Return current clipboard text, or empty string on failure."""
    if not _open_clipboard():
        log.warning("Cannot open clipboard for reading")
        return ""
    try:
        handle = _GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = _GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _GlobalUnlock(handle)
    finally:
        _CloseClipboard()


def _set_clipboard_text(text: str) -> bool:
    """Write *text* to the clipboard. Returns True on success."""
    if not _open_clipboard():
        log.warning("Cannot open clipboard for writing")
        return False
    try:
        _EmptyClipboard()
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = _GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            return False
        ptr = _GlobalLock(h_mem)
        if not ptr:
            return False
        ctypes.memmove(ptr, encoded, len(encoded))
        _GlobalUnlock(h_mem)
        _SetClipboardData(CF_UNICODETEXT, h_mem)
        return True
    finally:
        _CloseClipboard()


# ── Public API ────────────────────────────────────────────────────────────

def _save_recovery(text: str):
    """Append text to recovery_notes.txt as fallback when injection fails."""
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_RECOVERY_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
        log.info("Text saved to recovery_notes.txt")
    except Exception as exc:
        log.error("Failed to save recovery text: %s", exc)


def inject(text: str):
    """Paste *text* into the currently focused application.

    If clipboard write fails, the text is saved to recovery_notes.txt
    so the user never loses dictated content.
    """
    if not text:
        return

    # Save current clipboard content
    original = _get_clipboard_text()

    try:
        if not _set_clipboard_text(text):
            log.error("Failed to set clipboard text — saving to recovery file")
            _save_recovery(text)
            return
        time.sleep(0.05)

        # Simulate Ctrl+V to paste into the active app
        with _keyboard.pressed(Key.ctrl):
            _keyboard.press("v")
            _keyboard.release("v")

        time.sleep(0.10)
    finally:
        # Restore original clipboard
        _set_clipboard_text(original)
