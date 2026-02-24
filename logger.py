"""Centralised logging for Writher (console + rotating file)."""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "writher.log")


def setup(name: str = "writher") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # already initialised
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Rotating file handler (1 MB, 3 backups)
    fh = RotatingFileHandler(_LOG_FILE, maxBytes=1_048_576, backupCount=3,
                             encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup()
