"""
logger.py
─────────────────────────────────────────────────────────────────────────────
Logger centralizado. Escribe en consola y en archivo rotativo, con formato
consistente en toda la aplicación.
"""

import logging
from logging.handlers import RotatingFileHandler

from app.config import get_settings

_settings = get_settings()


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger configurado y listo para usar."""
    logger = logging.getLogger(name)

    if logger.handlers:
        # Ya configurado (evita handlers duplicados en recargas de uvicorn)
        return logger

    logger.setLevel(logging.DEBUG if _settings.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        file_handler = RotatingFileHandler(
            _settings.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Si el sistema de archivos es de solo lectura, seguimos solo con consola
        pass

    logger.propagate = False
    return logger
