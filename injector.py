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
from paths import RECOVERY_PATH
import config

_MAX_RECOVERY_SIZE = 512_000  # 500 KB max before rotation

_keyboard = Controller()

# ── Win32 clipboard constants & functions ─────────────────────────────────
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

CF_BITMAP = 2
CF_METAFILEPICT = 3
CF_PALETTE = 9
CF_UNICODETEXT = 13
CF_ENHMETAFILE = 14
CF_OWNERDISPLAY = 0x0080
CF_DSPBITMAP = 0x0082
CF_DSPMETAFILEPICT = 0x0083
CF_DSPENHMETAFILE = 0x008E
GMEM_MOVEABLE = 0x0002

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
_SetClipboardData.argtypes = [
    ctypes.wintypes.UINT,
    ctypes.wintypes.HANDLE,
]
_SetClipboardData.restype = ctypes.wintypes.HANDLE

_GetClipboardData = _user32.GetClipboardData
_GetClipboardData.argtypes = [ctypes.wintypes.UINT]
_GetClipboardData.restype = ctypes.wintypes.HANDLE

_EnumClipboardFormats = _user32.EnumClipboardFormats
_EnumClipboardFormats.argtypes = [ctypes.wintypes.UINT]
_EnumClipboardFormats.restype = ctypes.wintypes.UINT

_GetClipboardSequenceNumber = _user32.GetClipboardSequenceNumber
_GetClipboardSequenceNumber.argtypes = []
_GetClipboardSequenceNumber.restype = ctypes.wintypes.DWORD

_GlobalAlloc = _kernel32.GlobalAlloc
_GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
_GlobalAlloc.restype = ctypes.wintypes.HANDLE

_GlobalLock = _kernel32.GlobalLock
_GlobalLock.argtypes = [ctypes.wintypes.HANDLE]
_GlobalLock.restype = ctypes.c_void_p

_GlobalUnlock = _kernel32.GlobalUnlock
_GlobalUnlock.argtypes = [ctypes.wintypes.HANDLE]
_GlobalUnlock.restype = ctypes.wintypes.BOOL

_GlobalFree = _kernel32.GlobalFree
_GlobalFree.argtypes = [ctypes.wintypes.HANDLE]
_GlobalFree.restype = ctypes.wintypes.HANDLE

_ole32 = ctypes.windll.ole32
_OleDuplicateData = _ole32.OleDuplicateData
_OleDuplicateData.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
_OleDuplicateData.restype = ctypes.wintypes.HANDLE

_gdi32 = ctypes.windll.gdi32
_DeleteObject = _gdi32.DeleteObject
_DeleteObject.argtypes = [ctypes.wintypes.HANDLE]
_DeleteObject.restype = ctypes.wintypes.BOOL

_CopyEnhMetaFile = _gdi32.CopyEnhMetaFileW
_CopyEnhMetaFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.LPCWSTR]
_CopyEnhMetaFile.restype = ctypes.wintypes.HANDLE

_DeleteEnhMetaFile = _gdi32.DeleteEnhMetaFile
_DeleteEnhMetaFile.argtypes = [ctypes.wintypes.HANDLE]
_DeleteEnhMetaFile.restype = ctypes.wintypes.BOOL

_DeleteMetaFile = _gdi32.DeleteMetaFile
_DeleteMetaFile.argtypes = [ctypes.wintypes.HANDLE]
_DeleteMetaFile.restype = ctypes.wintypes.BOOL


class _METAFILEPICT(ctypes.Structure):
    _fields_ = [
        ("mm", ctypes.wintypes.LONG),
        ("xExt", ctypes.wintypes.LONG),
        ("yExt", ctypes.wintypes.LONG),
        ("hMF", ctypes.wintypes.HANDLE),
    ]

_MAX_RETRIES = 5
_RESTORE_RETRIES = 25
_SET_DATA_RETRIES = 3
_RETRY_DELAY = 0.02


# ── Clipboard helpers ─────────────────────────────────────────────────────

def _open_clipboard(retries: int = _MAX_RETRIES) -> bool:
    """Try to open the clipboard with retries (another app may hold it)."""
    for _ in range(retries):
        if _OpenClipboard(None):
            return True
        time.sleep(_RETRY_DELAY)
    return False


def _allocate_clipboard_text(text: str):
    """Allocate a movable UTF-16 block suitable for SetClipboardData."""
    encoded = text.encode("utf-16-le") + b"\x00\x00"
    h_mem = _GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h_mem:
        return None
    ptr = _GlobalLock(h_mem)
    if not ptr:
        _GlobalFree(h_mem)
        return None
    try:
        ctypes.memmove(ptr, encoded, len(encoded))
    finally:
        _GlobalUnlock(h_mem)
    return h_mem


def _duplicate_clipboard_handle(format_id: int, handle):
    """Duplicate one clipboard handle, including enhanced metafiles."""
    if format_id in {CF_ENHMETAFILE, CF_DSPENHMETAFILE}:
        return _CopyEnhMetaFile(handle, None)
    return _OleDuplicateData(handle, format_id, GMEM_MOVEABLE)


def _free_clipboard_handle(format_id: int, handle):
    """Free a duplicated handle that was not transferred to Windows."""
    if not handle:
        return
    if format_id in {CF_BITMAP, CF_PALETTE, CF_DSPBITMAP}:
        _DeleteObject(handle)
    elif format_id in {CF_ENHMETAFILE, CF_DSPENHMETAFILE}:
        _DeleteEnhMetaFile(handle)
    elif format_id in {CF_METAFILEPICT, CF_DSPMETAFILEPICT}:
        ptr = _GlobalLock(handle)
        if ptr:
            try:
                metafile = ctypes.cast(
                    ptr, ctypes.POINTER(_METAFILEPICT)).contents
                if metafile.hMF:
                    _DeleteMetaFile(metafile.hMF)
            finally:
                _GlobalUnlock(handle)
        _GlobalFree(handle)
    else:
        _GlobalFree(handle)


def _free_clipboard_snapshot(snapshot):
    for format_id, handle in snapshot:
        _free_clipboard_handle(format_id, handle)


def _capture_open_clipboard():
    """Duplicate each available format while the clipboard is open."""
    snapshot = []
    format_id = _EnumClipboardFormats(0)
    while format_id:
        # CF_OWNERDISPLAY is meaningful only while its original owner remains
        # the clipboard owner and has no portable data handle to duplicate.
        if format_id == CF_OWNERDISPLAY:
            log.error("Cannot safely preserve CF_OWNERDISPLAY clipboard data")
            _free_clipboard_snapshot(snapshot)
            return None

        handle = _GetClipboardData(format_id)
        if not handle:
            log.error("Cannot read clipboard format %d", format_id)
            _free_clipboard_snapshot(snapshot)
            return None
        duplicate = _duplicate_clipboard_handle(format_id, handle)
        if not duplicate:
            log.error("Cannot duplicate clipboard format %d", format_id)
            _free_clipboard_snapshot(snapshot)
            return None
        snapshot.append((format_id, duplicate))
        format_id = _EnumClipboardFormats(format_id)
    return snapshot


def _set_clipboard_data_with_retries(format_id: int, handle) -> bool:
    """Transfer one handle to Windows, retrying transient failures."""
    for attempt in range(_SET_DATA_RETRIES):
        if _SetClipboardData(format_id, handle):
            return True
        if attempt + 1 < _SET_DATA_RETRIES:
            time.sleep(_RETRY_DELAY)
    return False


def _swap_clipboard_for_text(text: str):
    """Atomically preserve all clipboard formats and replace them with text.

    Returns ``(snapshot, sequence_number)`` on success. The snapshot owns its
    handles until they are restored or explicitly freed.
    """
    text_handle = _allocate_clipboard_text(text)
    if not text_handle:
        return None
    if not _open_clipboard():
        log.warning("Cannot open clipboard for backup")
        _GlobalFree(text_handle)
        return None

    snapshot = None
    succeeded = False
    transferred = False
    try:
        snapshot = _capture_open_clipboard()
        if snapshot is None:
            return None
        if not _EmptyClipboard():
            return None
        if not _set_clipboard_data_with_retries(
                CF_UNICODETEXT, text_handle):
            # EmptyClipboard already destroyed the original. Restore the
            # snapshot immediately before reporting the failed swap.
            for format_id, handle in snapshot:
                if _set_clipboard_data_with_retries(format_id, handle):
                    continue
                _free_clipboard_handle(format_id, handle)
            snapshot = []
            return None
        transferred = True
        succeeded = True
    finally:
        _CloseClipboard()
        if not transferred:
            _GlobalFree(text_handle)
            if snapshot:
                _free_clipboard_snapshot(snapshot)
    if not succeeded:
        return None
    # Windows may synthesize compatible formats when the clipboard closes,
    # which can advance the sequence number. Record it only after CloseClipboard.
    return snapshot, _GetClipboardSequenceNumber()


def _open_clipboard_text() -> str | None:
    """Read Unicode text while the caller holds the clipboard open."""
    handle = _GetClipboardData(CF_UNICODETEXT)
    if not handle:
        return None
    ptr = _GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.wstring_at(ptr)
    finally:
        _GlobalUnlock(handle)


def _restore_clipboard(
        snapshot, expected_sequence: int, expected_text: str | None = None
) -> bool:
    """Restore a snapshot unless another program changed the clipboard."""
    if not _open_clipboard(_RESTORE_RETRIES):
        log.warning("Cannot open clipboard for restoration")
        _free_clipboard_snapshot(snapshot)
        return False

    remaining = list(snapshot)
    try:
        sequence_matches = (
            _GetClipboardSequenceNumber() == expected_sequence)
        text_matches = (
            expected_text is None or _open_clipboard_text() == expected_text)
        if not sequence_matches or not text_matches:
            log.info("Clipboard changed during paste; skipping restoration")
            return False
        if not _EmptyClipboard():
            return False

        restored_all = True
        while remaining:
            format_id, handle = remaining.pop(0)
            if not _set_clipboard_data_with_retries(format_id, handle):
                log.error("Cannot restore clipboard format %d", format_id)
                _free_clipboard_handle(format_id, handle)
                restored_all = False
                continue
            # Windows owns each successfully restored handle.
        return restored_all
    finally:
        _CloseClipboard()
        _free_clipboard_snapshot(remaining)


def _set_clipboard_text(text: str) -> bool:
    """Write *text* to the clipboard. Returns True on success."""
    h_mem = _allocate_clipboard_text(text)
    if not h_mem:
        return False

    if not _open_clipboard():
        log.warning("Cannot open clipboard for writing")
        _GlobalFree(h_mem)
        return False

    transferred = False
    try:
        if not _EmptyClipboard():
            return False
        if not _set_clipboard_data_with_retries(CF_UNICODETEXT, h_mem):
            return False
        transferred = True  # Windows owns h_mem after this succeeds.
        return True
    finally:
        _CloseClipboard()
        if not transferred:
            _GlobalFree(h_mem)


def _inject_via_clipboard(text: str) -> bool:
    """Paste *text* and optionally restore the previous clipboard data."""
    keep = getattr(config, "KEEP_TRANSCRIPT_IN_CLIPBOARD", False)
    swap = None

    try:
        if keep:
            ready = _set_clipboard_text(text)
        else:
            swap = _swap_clipboard_for_text(text)
            ready = swap is not None
        if not ready:
            log.error("Failed to set clipboard text (already saved to recovery)")
            return False
        time.sleep(0.05)

        with _keyboard.pressed(Key.ctrl):
            _keyboard.press("v")
            _keyboard.release("v")

        # The synthesized Ctrl+V is queued; allow asynchronous UI frameworks
        # time to consume the clipboard before restoring its original formats.
        time.sleep(getattr(config, "CLIPBOARD_RESTORE_DELAY", 0.5))
        return True
    finally:
        if swap is not None:
            snapshot, sequence = swap
            if not _restore_clipboard(snapshot, sequence, text):
                log.warning("Original clipboard could not be restored")


# ── Public API ────────────────────────────────────────────────────────────

def _save_recovery(text: str):
    """Append text to recovery_notes.txt. Rotates when file exceeds 500 KB."""
    try:
        # Rotate if too large
        if os.path.exists(RECOVERY_PATH):
            if os.path.getsize(RECOVERY_PATH) > _MAX_RECOVERY_SIZE:
                backup = RECOVERY_PATH + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(RECOVERY_PATH, backup)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(RECOVERY_PATH, "a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {text}\n")
    except Exception as exc:
        log.error("Failed to save recovery text: %s", exc)


def inject(text: str):
    """Paste *text* into the currently focused application.

    Every transcription is saved to recovery_notes.txt as a safety net,
    so dictated content is never lost even if the paste target ignores Ctrl+V.

    By default the user's supported clipboard contents are captured before the
    paste and restored afterwards. Setting
    ``config.KEEP_TRANSCRIPT_IN_CLIPBOARD`` to True skips the restore step.
    """
    if not text:
        return

    # Always save to recovery file — paste target may silently ignore Ctrl+V
    _save_recovery(text)

    _inject_via_clipboard(text)
