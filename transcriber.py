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

    def transcribe(self, audio_np: np.ndarray) -> str:
        segments, _info = self._model.transcribe(
            audio_np,
            language=config.LANGUAGE,
            beam_size=5,
            vad_filter=True,
            initial_prompt=get_initial_prompt(),
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return text.strip()
