"""Optional short audio cues for dictation recording start/stop (issue #24).

Off by default; enabled via the persisted ``audio_cues`` setting. The tones are
generated as PCM WAV in memory and played with
``winsound.PlaySound(SND_MEMORY | SND_ASYNC)`` on a daemon thread, so playback
never blocks the hotkey callback or delays recording. SND_MEMORY playback
proved more reliable than ``winsound.Beep`` when the default audio device
changes. Any playback failure is logged at debug level and swallowed — a
missing or busy audio device must never break dictation.
"""

import io
import math
import struct
import sys
import threading
import wave

from logger import log

_SAMPLE_RATE = 44100
_START_FREQ = 880.0   # A5 — higher tone: recording started
_STOP_FREQ = 440.0    # A4 — lower tone: recording stopped
_DURATION = 0.12      # seconds
_VOLUME = 0.35        # 0.0 .. 1.0

# Rendered WAV bytes are cached: the two tones never change, and the SND_ASYNC
# playback needs the buffer to stay alive for the duration of the sound.
_cache: dict[float, bytes] = {}


def _render_tone(freq: float) -> bytes:
    """Return a mono 16-bit PCM WAV of a short, fading sine wave at *freq*."""
    cached = _cache.get(freq)
    if cached is not None:
        return cached
    n = int(_SAMPLE_RATE * _DURATION)
    frames = bytearray()
    for i in range(n):
        # Linear fade-out avoids an audible click at the end of the tone.
        fade = 1.0 - (i / n)
        sample = _VOLUME * fade * math.sin(2.0 * math.pi * freq * i / _SAMPLE_RATE)
        frames += struct.pack("<h", int(sample * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        wav.writeframes(bytes(frames))
    data = buf.getvalue()
    _cache[freq] = data
    return data


def _play(freq: float):
    try:
        import winsound
        winsound.PlaySound(
            _render_tone(freq), winsound.SND_MEMORY | winsound.SND_ASYNC)
    except Exception as exc:
        log.debug("Audio cue playback failed: %s", exc)


def _play_async(freq: float):
    if sys.platform != "win32":
        return
    threading.Thread(target=_play, args=(freq,), daemon=True).start()


def play_start():
    """Play the 'recording started' cue (higher tone)."""
    _play_async(_START_FREQ)


def play_stop():
    """Play the 'recording stopped' cue (lower tone)."""
    _play_async(_STOP_FREQ)
