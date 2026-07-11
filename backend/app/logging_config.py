"""Structured logging setup (task D2).

WHY THIS EXISTS: in development you watch uvicorn's console, but a deployed
server has no terminal — when something breaks at 2am, the log FILE is the
only witness. This module configures Python's standard `logging` so that:

  - every line carries a timestamp, level, and logger name
  - lines go to BOTH the console (dev) and a rotating file (always)
  - the file rotates at 1 MB, keeping 3 old copies — logs can't silently
    eat the disk

"Rotating" means: when app.log hits the size cap it's renamed app.log.1
(bumping older ones) and a fresh app.log starts. Oldest copy is deleted.

Every module that wants to log does:
    logger = logging.getLogger(__name__)
    logger.info("something happened: %s", detail)
The %s style (not f-strings) defers string formatting until the log line is
actually emitted — free speed when a level is filtered out.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# backend/logs/app.log — next to the database, gitignored.
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"

# One line format everywhere: time, level, which module, message.
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging() -> None:
    """Configure the root logger with console + rotating-file handlers.

    Takes no input, returns nothing. Safe to call once at startup (main.py);
    calling twice would duplicate handlers, so we guard against that.
    """
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return  # already configured (uvicorn --reload re-imports modules)

    LOG_DIR.mkdir(exist_ok=True)  # first run: create backend/logs/
    formatter = logging.Formatter(FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,  # ~1 MB per file
        backupCount=3,       # keep app.log.1 … app.log.3, delete older
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    root.setLevel(logging.INFO)  # INFO and up; DEBUG stays silent
    root.addHandler(file_handler)
    root.addHandler(console)
