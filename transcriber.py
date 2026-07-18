import numpy as np
from faster_whisper import WhisperModel
import config
from logger import log
from replacements import get_initial_prompt


class Transcriber:
    def __init__(self):
        log.info("Loading Whisper model '%s'...", config.MODEL_SIZE)
        self._model = WhisperModel(
            config.MODEL_SIZE,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
        )
        log.info("Model loaded.")

    def transcribe_with_info(
            self, audio_np: np.ndarray) -> tuple[str, str | None, float | None]:
        language = config.WHISPER_LANGUAGE
        if language is None:
            log.info("Language detection: enabled (Auto).")
        else:
            log.info("Language detection: disabled; using fixed language: %s.",
                     language)
        segments, info = self._model.transcribe(
            audio_np,
            language=language,
            beam_size=5,
            vad_filter=True,
            initial_prompt=get_initial_prompt(),
        )
        detected = getattr(info, "language", None)
        probability = getattr(info, "language_probability", None)
        if detected and language is None:
            if probability is not None:
                log.info("Whisper detected language: %s (p=%.2f)",
                         detected, probability)
            else:
                log.info("Whisper detected language: %s", detected)
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip(), detected, probability

    def transcribe(self, audio_np: np.ndarray) -> str:
        text, _, _ = self.transcribe_with_info(audio_np)
        return text
