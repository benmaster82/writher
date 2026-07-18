import numpy as np
import sounddevice as sd
import threading
from time import perf_counter
import config
from logger import log


def _resolve_device(name: str | None) -> int | None:
    """Resolve a device name to a WASAPI device index at call time.

    Returns None (PortAudio's system default) if name is None or not found.
    Prefers WASAPI host API for explicitly selected microphones.
    Re-initializes PortAudio to get fresh device indices.
    """
    if not name:
        return None
    try:
        # Re-init PortAudio to get current indices after device hot-plug.
        sd._terminate()
        sd._initialize()

        host_apis = sd.query_hostapis()
        wasapi_idx = None
        for i, api in enumerate(host_apis):
            if "WASAPI" in api.get("name", ""):
                wasapi_idx = i
                break

        all_devs = sd.query_devices()

        # First pass: exact match on WASAPI
        for i, dev in enumerate(all_devs):
            if dev["max_input_channels"] <= 0:
                continue
            if wasapi_idx is not None and dev.get("hostapi") != wasapi_idx:
                continue
            if dev["name"] == name:
                return i

        # Second pass: partial match on WASAPI
        target = name.lower()
        for i, dev in enumerate(all_devs):
            if dev["max_input_channels"] <= 0:
                continue
            if wasapi_idx is not None and dev.get("hostapi") != wasapi_idx:
                continue
            if target in dev["name"].lower():
                return i

        # Third pass: any host API, exact match
        for i, dev in enumerate(all_devs):
            if dev["max_input_channels"] <= 0:
                continue
            if dev["name"] == name:
                return i

        log.warning("Microphone '%s' not found, falling back to default", name)
    except Exception as exc:
        log.warning("Device resolution failed: %s", exc)
    return None


class Recorder:
    def __init__(self):
        self._frames = []
        self._stream = None
        self._stream_device_name = None
        self._sample_rate = config.SAMPLE_RATE
        self._lock = threading.RLock()
        self._start_requested_at = None
        self._first_frame_pending = False
        self.recording = False
        self.on_started = None     # optional callback() after first audio block
        self.on_level = None       # optional callback(rms: float) set by main
        self.on_mic_error = None   # optional callback(msg: str) set by main

    def _callback(self, indata, frames, time, status):
        if self.recording:
            self._frames.append(indata.copy())
            if self._first_frame_pending:
                self._first_frame_pending = False
                if self._start_requested_at is not None:
                    log.info("First microphone audio received after %.0fms.",
                             (perf_counter() - self._start_requested_at) * 1000)
                if self.on_started is not None:
                    try:
                        self.on_started()
                    except Exception as exc:
                        log.warning("Microphone-start notification failed: %s",
                                    exc)
            if self.on_level is not None:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self.on_level(rms)

    def _close_stream(self):
        stream, self._stream = self._stream, None
        self._stream_device_name = None
        if stream is None:
            return
        try:
            if stream.active:
                stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def _open_stream(self, device_name):
        device_idx = _resolve_device(device_name)
        log.info("Opening mic: name=%s resolved_idx=%s", device_name, device_idx)

        sample_rates = [config.SAMPLE_RATE]
        if device_idx is not None:
            dev_info = sd.query_devices(device_idx)
            native_rate = int(dev_info.get("default_samplerate", 48000))
            if native_rate not in sample_rates:
                sample_rates.append(native_rate)
        elif 48000 not in sample_rates:
            sample_rates.append(48000)

        last_error = None
        for sample_rate in sample_rates:
            try:
                stream = sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    device=device_idx,
                    callback=self._callback,
                    latency="low",
                )
                self._stream = stream
                self._stream_device_name = device_name
                self._sample_rate = sample_rate
                if sample_rate != config.SAMPLE_RATE:
                    log.info(
                        "Using device native sample rate: %d Hz "
                        "(will resample to %d)",
                        sample_rate, config.SAMPLE_RATE)
                return
            except (sd.PortAudioError, OSError) as exc:
                last_error = exc
                log.info("Could not open device=%s at %d Hz: %s",
                         device_idx, sample_rate, exc)

        raise last_error or OSError("No microphone input device available")

    def prepare(self) -> bool:
        """Open the configured microphone once, leaving its stream stopped."""
        with self._lock:
            if self.recording:
                return True
            device_name = getattr(config, "MIC_DEVICE_NAME", None)
            if self._stream is not None and self._stream_device_name == device_name:
                return True
            self._close_stream()
            started = perf_counter()
            try:
                self._open_stream(device_name)
                log.info("Microphone prepared in %.0fms.",
                         (perf_counter() - started) * 1000)
                return True
            except Exception as exc:
                log.error("Failed to prepare microphone: %s", exc)
                self._close_stream()
                if self.on_mic_error:
                    self.on_mic_error("🎤 No microphone detected")
                return False

    def start(self):
        with self._lock:
            if self.recording:
                return True
            self._frames = []
            if not self.prepare():
                return False
            self._start_requested_at = perf_counter()
            self._first_frame_pending = True
            self.recording = True
            try:
                self._stream.start()
                log.info("Microphone start returned after %.0fms.",
                         (perf_counter() - self._start_requested_at) * 1000)
                return True
            except Exception as exc:
                log.warning("Prepared microphone could not start, reopening: %s",
                            exc)
                self.recording = False
                self._close_stream()
                if not self.prepare():
                    return False
                try:
                    self._start_requested_at = perf_counter()
                    self._first_frame_pending = True
                    self.recording = True
                    self._stream.start()
                    return True
                except Exception as retry_exc:
                    log.error("Failed to start microphone: %s", retry_exc)
                    self.recording = False
                    self._close_stream()
                    if self.on_mic_error:
                        self.on_mic_error("🎤 No microphone detected")
                    return False

    def stop(self):
        with self._lock:
            if not self.recording:
                return None
            self.recording = False
            if self._stream is not None:
                self._stream.stop()
            if not self._frames:
                return None
            audio = np.concatenate(self._frames, axis=0).flatten()

            # Resample to 16kHz if recorded at a different rate
            target_rate = config.SAMPLE_RATE
            if self._sample_rate != target_rate:
                # Simple linear interpolation resampling
                duration = len(audio) / self._sample_rate
                target_len = int(duration * target_rate)
                indices = np.linspace(0, len(audio) - 1, target_len)
                audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
                log.info("Resampled audio from %d Hz to %d Hz (%d samples)",
                         self._sample_rate, target_rate, target_len)

            return audio

    def close(self):
        """Stop recording and release the prepared microphone stream."""
        with self._lock:
            if self.recording:
                self.recording = False
                try:
                    self._stream.stop()
                except Exception:
                    pass
            self._close_stream()
