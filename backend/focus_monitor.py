from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from backend.hyprland import Hyprland
    from backend.mpvpaper import Mpvpaper

logger = logging.getLogger(__name__)


class FocusMonitor(QObject):
    """Monitoriza Hyprland y pausa los fondos animados solo cuando una
    ventana a pantalla completa cubre totalmente el escritorio.

    En Hyprland las ventanas tiled o floating normalmente dejan visible
    el wallpaper, por lo que pausar con cualquier ventana enfocada es
    demasiado agresivo.
    """

    def __init__(
        self,
        hyprland: Hyprland,
        mpvpaper: Mpvpaper,
        check_interval_ms: int = 2000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._hyprland = hyprland
        self._mpvpaper = mpvpaper
        self._check_interval = check_interval_ms
        self._enabled = False
        self._paused = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self._timer.start(self._check_interval)
        else:
            self._timer.stop()
            self._resume()

    def start(self) -> None:
        self.set_enabled(True)

    def stop(self) -> None:
        self.set_enabled(False)

    def _focused_workspace_id(self) -> int | None:
        """Devuelve el ID del workspace activo en el monitor enfocado."""
        for m in self._hyprland.list_monitors():
            if m.get("focused"):
                return m.get("activeWorkspace", {}).get("id")
        return None

    def _check(self) -> None:
        if not self._enabled:
            return
        try:
            ws = self._focused_workspace_id()
            if ws is None:
                return

            fullscreen = self._hyprland.is_fullscreen_on_workspace(ws)

            if fullscreen and not self._paused:
                logger.debug("FocusMonitor: fullscreen window, pausing wallpaper")
                self._mpvpaper.pause()
                self._paused = True
            elif not fullscreen and self._paused:
                logger.debug("FocusMonitor: no fullscreen, resuming wallpaper")
                self._mpvpaper.resume()
                self._paused = False
        except Exception:
            logger.debug("FocusMonitor: check failed", exc_info=True)

    def _resume(self) -> None:
        if self._paused:
            self._mpvpaper.resume()
            self._paused = False
