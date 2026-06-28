"""
Notifications
=============

Notificaciones de escritorio compatibles con Wayland/Hyprland.

Se intenta usar ``notify-send`` (libnotify) por ser el estándar de facto
en Linux. Si no está disponible, se registra un aviso en el log y la
operación se ignora silenciosamente.
"""

from __future__ import annotations

import logging
import subprocess
from enum import IntEnum
from shutil import which
from typing import Final

logger = logging.getLogger(__name__)

APP_NAME: Final[str] = "Frostwall"


class NotificationLevel(IntEnum):
    """Niveles de urgencia según la spec de Freedesktop."""

    LOW = 0
    NORMAL = 1
    CRITICAL = 2

    def to_notify_urgency(self) -> str:
        """Convierte a la cadena esperada por ``notify-send -u``."""
        return {
            NotificationLevel.LOW: "low",
            NotificationLevel.NORMAL: "normal",
            NotificationLevel.CRITICAL: "critical",
        }[self]


class Notifier:
    """Envía notificaciones de escritorio.

    Attributes:
        enabled: Si ``False``, todas las llamadas son no-ops.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._available: bool | None = None

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def send(
        self,
        title: str,
        message: str,
        *,
        level: NotificationLevel = NotificationLevel.NORMAL,
        icon: str | None = None,
        timeout_ms: int = 4000,
    ) -> bool:
        """Envía una notificación al escritorio.

        Args:
            title: Título breve.
            message: Cuerpo del mensaje.
            level: Nivel de urgencia.
            icon: Nombre o ruta de icono (opcional).
            timeout_ms: Tiempo en pantalla en milisegundos.

        Returns:
            ``True`` si la notificación se envió correctamente.
        """
        if not self.enabled:
            logger.debug("Notifications disabled: %s - %s", title, message)
            return False

        if not self._check_available():
            return False

        cmd = [
            "notify-send",
            "-a", APP_NAME,
            "-u", level.to_notify_urgency(),
            "-t", str(timeout_ms),
        ]
        if icon:
            cmd.extend(["-i", icon])
        cmd.extend([title, message])

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            logger.debug("Notification sent: %s", title)
            return True
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "notify-send falló: %s",
                exc.stderr.decode("utf-8", "ignore")[:200] or "error desconocido",
            )
        except subprocess.TimeoutExpired:
            logger.warning("notify-send timed out")
        except FileNotFoundError:
            self._available = False
        return False

    def info(self, title: str, message: str) -> bool:
        """Atajo para notificaciones informativas."""
        return self.send(title, message, level=NotificationLevel.LOW)

    def warning(self, title: str, message: str) -> bool:
        """Atajo para advertencias."""
        return self.send(title, message, level=NotificationLevel.NORMAL)

    def error(self, title: str, message: str) -> bool:
        """Atajo para errores críticos."""
        return self.send(title, message, level=NotificationLevel.CRITICAL)

    # ------------------------------------------------------------------ #
    # Privados
    # ------------------------------------------------------------------ #
    def _check_available(self) -> bool:
        """Comprueba (con caché) si ``notify-send`` está disponible."""
        if self._available is None:
            self._available = which("notify-send") is not None
            if not self._available:
                logger.info(
                    "notify-send no disponible; las notificaciones se omitirán"
                )
        return self._available
