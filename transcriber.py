import numpy as np
from faster_whisper import WhisperModel
import config
from logger import log
from replacements import get_initial_prompt


class Transcriber:
    def __init__(self, local_files_only: bool = False):
        """Load the Whisper model.

        With ``local_files_only=True`` the model is loaded straight from the
        HuggingFace cache without any network access — otherwise a slow or
        blocked connection to huggingface.co can hang startup even though
        the model is already fully on disk.
        """
        log.info("Loading Whisper model '%s'%s...", config.MODEL_SIZE,
                 " (local cache only)" if local_files_only else "")
        try:
            self._model = WhisperModel(
                config.MODEL_SIZE,
                device=config.DEVICE,
                compute_type=config.COMPUTE_TYPE,
                local_files_only=local_files_only,
            )
        except Exception:
            if not local_files_only:
                raise
            # The cache looked complete but was not usable — retry once
            # with network access instead of failing startup.
            log.warning("Local-only model load failed; retrying with "
                        "network access.")
            self._model = WhisperModel(
                config.MODEL_SIZE,
                device=config.DEVICE,
                compute_type=config.COMPUTE_TYPE,
            )
        log.info("Model loaded.")

    def transcribe(self, audio_np: np.ndarray) -> str:
        segments, info = self._model.transcribe(
            audio_np,
            language=config.WHISPER_LANGUAGE,
            beam_size=5,
            vad_filter=True,
            initial_prompt=get_initial_prompt(),
        )
        detected = getattr(info, "language", None)
        probability = getattr(info, "language_probability", None)
        if detected:
            if probability is not None:
                log.info("Whisper detected language: %s (p=%.2f)",
                         detected, probability)
            else:
                log.info("Whisper detected language: %s", detected)
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()
