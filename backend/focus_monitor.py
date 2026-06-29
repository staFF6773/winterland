from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from backend.hyprland import Hyprland
    from backend.mpvpaper import Mpvpaper
    from config.settings import Settings

logger = logging.getLogger(__name__)


class FocusMonitor(QObject):
    """Pausa los fondos animados cuando no se están viendo o usando.

    Dos motivos independientes y coordinados de pausa:

    * ``fullscreen``: una ventana a pantalla completa cubre el escritorio
      en el workspace activo. Configurable con
      ``mpvpaper.pause_on_focus_loss``.
    * ``idle``: sin cambios de ventana/workspace durante N minutos.
      Configurable con ``mpvpaper.idle_pause_enabled`` y
      ``mpvpaper.idle_pause_minutes``. Es de disparo único: tras pausar,
      sólo se reanuda al detectar actividad (cambio de ventana/workspace),
      respetando así una reanudación manual del usuario.

    El wallpaper se reanuda únicamente cuando ningún motivo está activo.
    La configuración se lee en vivo cada iteración, por lo que los cambios
    hechos en el diálogo de ajustes surten efecto sin reiniciar.
    """

    def __init__(
        self,
        hyprland: Hyprland,
        mpvpaper: Mpvpaper,
        settings: Settings | None = None,
        check_interval_ms: int = 3000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._hyprland = hyprland
        self._mpvpaper = mpvpaper
        self._settings = settings
        self._check_interval = check_interval_ms
        self._enabled = False
        self._paused_by_monitor = False  # ¿hemos pausado nosotros mpv?

        # Seguimiento de inactividad.
        self._idle_hash: str | None = None
        self._last_activity: float = time.monotonic()
        self._idle_paused = False

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

    # ------------------------------------------------------------------ #
    # Configuración en vivo
    # ------------------------------------------------------------------ #
    def _fullscreen_enabled(self) -> bool:
        if self._settings is None:
            return True
        return bool(self._settings.get("mpvpaper.pause_on_focus_loss", True))

    def _idle_enabled(self) -> bool:
        if self._settings is None:
            return False
        return bool(self._settings.get("mpvpaper.idle_pause_enabled", False))

    def _idle_seconds(self) -> float:
        if self._settings is None:
            return 300.0
        return max(1, int(self._settings.get("mpvpaper.idle_pause_minutes", 5))) * 60

    # ------------------------------------------------------------------ #
    # Bucle principal
    # ------------------------------------------------------------------ #
    def _check(self) -> None:
        if not self._enabled:
            return

        # Corte barato: si no hay wallpaper animado corriendo, no hay nada
        # que hacer. is_running() usa comprobaciones de PID, no escanea la
        # tabla de procesos.
        if not self._mpvpaper.is_running():
            self._reset_idle()
            self._resume()
            return

        try:
            ws = self._hyprland.focused_workspace_id()
            if ws is None:
                return

            reasons: set[str] = set()

            if self._fullscreen_enabled() and self._hyprland.is_fullscreen_on_workspace(ws):
                reasons.add("fullscreen")

            if self._idle_enabled():
                self._update_idle(ws)
                if self._idle_paused:
                    reasons.add("idle")

            self._apply_reasons(reasons)
        except Exception:
            logger.debug("FocusMonitor: check failed", exc_info=True)

    def _update_idle(self, workspace_id: int | None) -> None:
        """Actualiza el estado de inactividad.

        Dispara la pausa por inactividad una sola vez; se resetea al
        detectar cualquier cambio de ventana/workspace.
        """
        current = self._idle_hash_for(workspace_id)
        if current != self._idle_hash:
            # Actividad: resetea el temporizador de inactividad.
            self._idle_hash = current
            self._last_activity = time.monotonic()
            self._idle_paused = False
            logger.debug("FocusMonitor: activity detected, idle reset")
            return

        if not self._idle_paused:
            elapsed = time.monotonic() - self._last_activity
            if elapsed >= self._idle_seconds():
                self._idle_paused = True
                logger.debug("FocusMonitor: idle timeout reached, pausing wallpaper")

    def _idle_hash_for(self, workspace_id: int | None) -> str:
        """Hash de actividad: workspace + ventana enfocada."""
        window = self._hyprland.active_window() or {}
        cls = str(window.get("class", ""))
        title = str(window.get("title", ""))
        return f"{workspace_id}:{cls}:{title}"

    def _reset_idle(self) -> None:
        self._idle_hash = None
        self._last_activity = time.monotonic()
        self._idle_paused = False

    # ------------------------------------------------------------------ #
    # Pausa / reanudación coordinada
    # ------------------------------------------------------------------ #
    def _apply_reasons(self, reasons: set[str]) -> None:
        should_pause = bool(reasons)
        if should_pause and not self._paused_by_monitor:
            logger.debug("FocusMonitor: pausing wallpaper (reasons=%s)", reasons)
            self._mpvpaper.pause()
            self._paused_by_monitor = True
        elif not should_pause and self._paused_by_monitor:
            logger.debug("FocusMonitor: resuming wallpaper (no reasons)")
            self._mpvpaper.resume()
            self._paused_by_monitor = False

    def _resume(self) -> None:
        if self._paused_by_monitor:
            self._mpvpaper.resume()
            self._paused_by_monitor = False
