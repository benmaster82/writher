import numpy as np
import sounddevice as sd
import config
from logger import log


def _resolve_device(name: str | None) -> int | None:
    """Resolve a device name to a WASAPI device index at call time.

    Returns None (system default) if name is None or not found.
    Prefers WASAPI host API for reliable Windows audio.
    Re-initializes PortAudio to get fresh device indices.
    """
    if not name:
        return None
    try:
        # Re-init PortAudio to get current indices
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
        self.recording = False
        self.on_level = None       # optional callback(rms: float) set by main
        self.on_mic_error = None   # optional callback(msg: str) set by main

    def _callback(self, indata, frames, time, status):
        if self.recording:
            self._frames.append(indata.copy())
            if self.on_level is not None:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self.on_level(rms)

    def start(self):
        if self.recording:
            return
        self._frames = []
        self.recording = True
        try:
            device_name = getattr(config, "MIC_DEVICE_NAME", None)
            device_idx = _resolve_device(device_name)
            log.info("Opening mic: name=%s resolved_idx=%s", device_name, device_idx)

            # Try configured sample rate first, fall back to device default
            sample_rate = config.SAMPLE_RATE
            if device_idx is not None:
                try:
                    dev_info = sd.query_devices(device_idx)
                    dev_sr = int(dev_info.get("default_samplerate", sample_rate))
                    if dev_sr != sample_rate:
                        log.info("Device default sample rate is %d, using it instead of %d",
                                 dev_sr, sample_rate)
                        sample_rate = dev_sr
                except Exception:
                    pass

            self._stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                device=device_idx,
                callback=self._callback,
            )
            self._stream.start()
            self._sample_rate = sample_rate  # store for transcriber
        except (sd.PortAudioError, OSError, Exception) as exc:
            log.error("Failed to open microphone: %s", exc)
            self.recording = False
            self._stream = None
            if self.on_mic_error:
                self.on_mic_error("🎤 No microphone detected")

    def stop(self):
        if not self.recording:
            return None
        self.recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return None
        audio = np.concatenate(self._frames, axis=0).flatten()
        return audio
