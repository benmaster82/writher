import importlib.util
import os
import sys

import numpy as np
from faster_whisper import WhisperModel
import config
from logger import log
from replacements import get_initial_prompt


def _nvidia_bin_dirs() -> list[str]:
    """Return bin directories of pip-installed NVIDIA CUDA packages.

    Packages like nvidia-cublas-cu12 ship their DLLs under
    site-packages/nvidia/<lib>/bin, which the Windows loader does not
    search by default (issue #21).
    """
    try:
        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        return []
    if spec is None or not spec.submodule_search_locations:
        return []
    dirs = []
    for root in spec.submodule_search_locations:
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue
        for entry in entries:
            bin_dir = os.path.join(entry.path, "bin")
            if entry.is_dir() and os.path.isdir(bin_dir):
                dirs.append(bin_dir)
    return dirs


# Keep the handles alive: letting them be garbage-collected removes the
# directories from the DLL search path again.
_dll_dir_handles = []


def _expose_nvidia_dlls():
    """Make pip-installed CUDA runtime DLLs loadable (Windows only).

    add_dll_directory() covers DLLs loaded when the model is constructed,
    but CTranslate2 loads cuBLAS lazily on the first inference call, and on
    some GPU architectures (e.g. Ada / RTX 40xx) that lazy load only honours
    the process PATH — not the registered directories. So we do both:
    register each directory and prepend it to PATH. Verified on RTX 4070
    by @MaxiKingXXL in issue #21.
    """
    if sys.platform != "win32" or _dll_dir_handles:
        return
    added = []
    for bin_dir in _nvidia_bin_dirs():
        try:
            _dll_dir_handles.append(os.add_dll_directory(bin_dir))
            added.append(bin_dir)
            log.info("Added NVIDIA DLL directory: %s", bin_dir)
        except OSError as exc:
            log.warning("Could not add DLL directory %s: %s", bin_dir, exc)
    if added:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(
            added + ([current_path] if current_path else []))


class Transcriber:
    def __init__(self, local_files_only: bool = False):
        """Load the Whisper model.

        With ``local_files_only=True`` the model is loaded straight from the
        HuggingFace cache without any network access — otherwise a slow or
        blocked connection to huggingface.co can hang startup even though
        the model is already fully on disk.
        """
        if config.DEVICE == "cuda":
            _expose_nvidia_dlls()
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
