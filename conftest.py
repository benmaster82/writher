"""Shared pytest configuration.

Keeps the test suite from touching the real application log: the module
logger writes to %APPDATA%\\WritHer\\writher.log (or the project dir when
running from source), and we don't want test runs mutating it. Redirect
the file handler to a temporary file for the whole session (issue #22).
"""

import logging
import tempfile

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_log_file():
    logger = logging.getLogger("writher")
    file_handlers = [h for h in logger.handlers
                     if isinstance(h, logging.FileHandler)]
    originals = [(h, h.baseFilename) for h in file_handlers]
    tmp = tempfile.NamedTemporaryFile(
        prefix="writher-test-", suffix=".log", delete=False)
    tmp.close()
    for h in file_handlers:
        h.close()
        h.baseFilename = tmp.name
        h.stream = None  # reopened lazily on next emit
    try:
        yield
    finally:
        for h, path in originals:
            h.close()
            h.baseFilename = path
            h.stream = None
