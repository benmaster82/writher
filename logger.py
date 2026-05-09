"""Centralised logging for Writher (console + rotating file)."""

import logging
from logging.handlers import RotatingFileHandler
from paths import LOG_PATH


def setup(name: str = "writher") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # already initialised
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Rotating file handler (1 MB, 3 backups)
    fh = RotatingFileHandler(LOG_PATH, maxBytes=1_048_576, backupCount=3,
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
