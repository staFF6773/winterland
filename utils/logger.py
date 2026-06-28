"""
Logger
======

Configuración centralizada de :mod:`logging` para Wallpaper Manager.

Se generan dos manejadores:

* **Consola** (stderr) con formato compacto y colores opcionales.
* **Archivo rotativo** en ``~/.cache/wallpaper-manager/logs/app.log``.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ruta por defecto de logs.
DEFAULT_LOG_DIR = Path(
    os.environ.get(
        "FROSTWALL_LOG_DIR",
        os.environ.get(
            "WALLPAPER_MANAGER_LOG_DIR",
            os.path.expanduser("~/.cache/frostwall/logs"),
        ),
    )
)

# Formato común.
_FORMAT = "%(asctime)s | %(name)-32s | %(levelname)-8s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Colores ANSI para consola (no se usan si NO_COLOR está definido).
_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[37m",      # blanco
    "WARNING": "\033[33m",   # amarillo
    "ERROR": "\033[31m",     # rojo
    "CRITICAL": "\033[1;31m",  # rojo brillante
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Formateador que añade colores ANSI según el nivel."""

    def __init__(self, *, use_color: bool = True) -> None:
        super().__init__(fmt=_FORMAT, datefmt=_DATEFMT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        message = super().format(record)
        if not self.use_color:
            return message
        color = _COLORS.get(record.levelname, "")
        if not color:
            return message
        return f"{color}{message}{_RESET}"


def setup_logging(
    level: int | str = logging.INFO,
    *,
    log_dir: Path | str | None = None,
    enable_file: bool = True,
    enable_color: bool | None = None,
) -> logging.Logger:
    """Configura el sistema de logging de la aplicación.

    Args:
        level: Nivel mínimo a registrar.
        log_dir: Carpeta destino de logs. Si se omite usa :data:`DEFAULT_LOG_DIR`.
        enable_file: Si ``True``, escribe logs a un archivo rotativo.
        enable_color: Si ``True``, usa colores en consola. ``None`` los
            activa automáticamente si la salida es un TTY y ``NO_COLOR``
            no está definido.

    Returns:
        Logger raíz de la aplicación.
    """
    log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    if enable_color is None:
        enable_color = sys.stderr.isatty() and "NO_COLOR" not in os.environ

    root = logging.getLogger("frostwall")
    if getattr(root, "_wallpaper_configured", False):
        # Ya configurado: solo ajustamos el nivel.
        root.setLevel(level)
        return root

    root.setLevel(level)
    root.propagate = False

    # Handler de consola.
    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(_ColorFormatter(use_color=enable_color))
    root.addHandler(console)

    # Handler de archivo rotativo (5 MB, 3 copias).
    if enable_file:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
            root.addHandler(file_handler)
        except OSError:
            # Si no podemos escribir logs, seguimos funcionando.
            root.warning("No se pudo crear el archivo de log en %s", log_dir)

    root._wallpaper_configured = True  # type: ignore[attr-defined]
    return root


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger hijo del logger raíz de la aplicación.

    Args:
        name: Nombre del logger. Suele ser ``__name__``.

    Returns:
        Instancia de :class:`logging.Logger`.
    """
    if not name.startswith("frostwall"):
        name = f"frostwall.{name}"
    return logging.getLogger(name)
