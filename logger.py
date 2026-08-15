import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with console + rotating file handlers.

    Safe to call multiple times — skipped if already configured.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)
    fmt = logging.Formatter(LOG_FORMAT)

    # Windows console defaults to the OEM codepage, not UTF-8 — without this,
    # Cyrillic log lines become mojibake once run_service.bat redirects
    # stderr into service.log (2>&1).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    LOG_DIR.mkdir(exist_ok=True)
    rotating = logging.handlers.RotatingFileHandler(
        LOG_DIR / "havas.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
        encoding="utf-8",
    )
    rotating.setFormatter(fmt)
    root.addHandler(rotating)
