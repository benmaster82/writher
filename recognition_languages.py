"""Whisper recognition-language codes and display names."""

import ctypes

from faster_whisper.tokenizer import _LANGUAGE_CODES


SUPPORTED_LANGUAGE_CODES = tuple(_LANGUAGE_CODES)
_LOCALE_SENGLISHLANGUAGENAME = 0x1001


def language_display_name(code: str) -> str:
    """Return a readable Windows language name with the Whisper code."""
    normalized = (code or "").strip().lower()
    if not normalized:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(128)
        length = ctypes.windll.kernel32.GetLocaleInfoEx(
            normalized,
            _LOCALE_SENGLISHLANGUAGENAME,
            buffer,
            len(buffer),
        )
        name = buffer.value.strip() if length else ""
        if name and not name.startswith("Unknown "):
            return f"{name} ({normalized.upper()})"
    except Exception:
        pass
    return normalized.upper()
