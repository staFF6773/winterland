"""
Wallpaper Manager
=================

Gestor central que orquesta todos los componentes del backend.

Expone una API unificada para aplicar fondos (estáticos o animados),
rotar wallpapers, gestionar favoritos/historial/playlists y notificar
cambios a la GUI mediante señales Qt.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from pathlib import Path
from typing import Any, Callable

from config.settings import Settings
from utils.file_utils import expand, is_animated, is_image
from utils.notifications import Notifier
from backend.favorites import Favorites
from backend.focus_monitor import FocusMonitor
from backend.history import History
from backend.hyprland import Hyprland
from backend.hyprpaper import Hyprpaper, HyprpaperError
from backend.library import Library, WallpaperItem, WallpaperType
from backend.monitor import MonitorManager
from backend.mpvpaper import Mpvpaper, MpvpaperError
from backend.playlist import PlaylistManager

logger = logging.getLogger(__name__)


class WallpaperManagerError(RuntimeError):
    """Error en operaciones del gestor central."""


class WallpaperManager:
    """Orquestador del backend de Wallpaper Manager.

    Conecta :class:`Library`, :class:`Favorites`, :class:`History`,
    :class:`PlaylistManager`, :class:`Hyprpaper` y :class:`Mpvpaper`.

    Attributes:
        settings: Configuración global.
        library: Biblioteca de wallpapers.
        favorites: Favoritos.
        history: Historial de aplicación.
        playlists: Gestor de playlists.
        hyprpaper: Controlador de hyprpaper.
        mpvpaper: Controlador de mpvpaper.
        monitors: Gestor de monitores.
        notifier: Notificador de escritorio.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.library = Library(
            self.settings.expand_path(self.settings.get("wallpapers.folder", "")),
            recursive=bool(self.settings.get("wallpapers.recursive_scan", True)),
            image_extensions=self.settings.get("wallpapers.supported_image_extensions"),
            video_extensions=self.settings.get("wallpapers.supported_video_extensions"),
        )
        self.favorites = Favorites()
        self.history = History(max_entries=int(self.settings.get("history.max_entries", 100)))
        self.playlists = PlaylistManager()
        self.hyprland = Hyprland()
        self.monitors = MonitorManager(self.hyprland)
        self.hyprpaper = Hyprpaper(
            executable=str(self.settings.get("hyprpaper.executable", "hyprpaper")),
            config_path=self.settings.expand_path(
                self.settings.get("hyprpaper.config_path", "")
            ),
            hyprland=self.hyprland,
        )
        self.mpvpaper = Mpvpaper(
            executable=str(self.settings.get("mpvpaper.executable", "mpvpaper")),
            mpv_options=str(self.settings.get("mpvpaper.mpv_options", "")),
            hyprland=self.hyprland,
        )
        self.notifier = Notifier(enabled=bool(self.settings.get("notifications.enabled", True)))

        # Monitor de foco/inactividad para pausar fondos animados.
        self.focus_monitor: FocusMonitor | None = None

        # Estado interno.
        self._rotation_thread: threading.Thread | None = None
        self._rotation_stop = threading.Event()
        self._callbacks: list[Callable[[str, dict[str, Any]], None]] = []
        self._callback_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Callbacks para la GUI
    # ------------------------------------------------------------------ #
    def add_listener(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Registra un callback para eventos del gestor.

        El callback recibe ``(event_name, payload)``.
        """
        with self._callback_lock:
            self._callbacks.append(callback)

    def _emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Notifica un evento a todos los listeners."""
        payload = payload or {}
        with self._callback_lock:
            callbacks = list(self._callbacks)
        for callback in callbacks:
            try:
                callback(event, payload)
            except Exception:  # noqa: BLE001
                logger.exception("Error en listener de evento %s", event)

    # ------------------------------------------------------------------ #
    # Aplicación de wallpapers
    # ------------------------------------------------------------------ #
    def apply(
        self,
        path: Path | str,
        *,
        monitor: str = "",
        record_history: bool = True,
        notify: bool = True,
    ) -> bool:
        """Aplica un wallpaper (estático o animado) a un monitor.

        Args:
            path: Ruta del wallpaper.
            monitor: Monitor destino (vacío = todos o primario).
            record_history: Si ``True``, añade al historial.
            notify: Si ``True``, envía notificación de escritorio.

        Returns:
            ``True`` si se aplicó correctamente.

        Raises:
            WallpaperManagerError: Si el archivo no es válido.
        """
        wallpaper_path = expand(path)
        if not wallpaper_path.exists():
            raise WallpaperManagerError(f"El archivo no existe: {wallpaper_path}")

        target_monitor = monitor or self._default_monitor_name()
        success = False
        wallpaper_type = "image"

        if is_animated(wallpaper_path):
            # Detener hyprpaper en ese monitor para evitar conflictos.
            try:
                self.hyprpaper.unload()
            except HyprpaperError:
                pass
            try:
                mpv_opts = str(self.settings.get("mpvpaper.mpv_options", ""))
                max_fps = self.settings.get("mpvpaper.max_fps")
                success = self.mpvpaper.play(
                    wallpaper_path,
                    target_monitor,
                    mpv_options=mpv_opts,
                    max_fps=max_fps if isinstance(max_fps, int) else None,
                )
                wallpaper_type = "video"
            except MpvpaperError as exc:
                logger.error("Error aplicando fondo animado: %s", exc)
                self.notifier.error("Animated wallpaper error", str(exc))
                raise WallpaperManagerError(str(exc)) from exc
        elif is_image(wallpaper_path):
            # Detener mpvpaper en ese monitor.
            self.mpvpaper.stop(target_monitor)
            try:
                success = self.hyprpaper.apply(wallpaper_path, target_monitor)
                wallpaper_type = "image"
            except HyprpaperError as exc:
                logger.error("Error applying static wallpaper: %s", exc)
                self.notifier.error("Static wallpaper error", str(exc))
                raise WallpaperManagerError(str(exc)) from exc
        else:
            raise WallpaperManagerError(
                f"Formato no soportado: {wallpaper_path.suffix}"
            )

        if success:
            if record_history:
                self.history.add(
                    wallpaper_path,
                    monitor=target_monitor,
                    type_=wallpaper_type,
                )
                self._save_last_wallpaper(wallpaper_path, target_monitor)

            if notify and self.settings.get("notifications.on_wallpaper_change", True):
                self.notifier.info(
                    "Wallpaper updated",
                    f"{wallpaper_path.name} on {target_monitor or 'all'}",
                )
            self._emit("wallpaper_applied", {
                "path": str(wallpaper_path),
                "monitor": target_monitor,
                "type": wallpaper_type,
            })
        return success

    def apply_to_all_monitors(self, path: Path | str) -> int:
        """Aplica el mismo wallpaper a todos los monitores conectados.

        Returns:
            Número de monitores a los que se aplicó.
        """
        count = 0
        for monitor in self.monitors.refresh():
            try:
                if self.apply(path, monitor=monitor.name, notify=False):
                    count += 1
            except WallpaperManagerError as exc:
                logger.warning("No se pudo aplicar a %s: %s", monitor.name, exc)
        if count and self.settings.get("notifications.on_wallpaper_change", True):
            self.notifier.info(
                "Wallpaper applied to all monitors",
                f"{Path(path).name} → {count} monitor(s)",
            )
        return count

    # ------------------------------------------------------------------ #
    # Restauración
    # ------------------------------------------------------------------ #
    def restore_last(self) -> bool:
        """Restaura los últimos wallpapers aplicados por monitor.

        Returns:
            ``True`` si se restauró al menos un fondo.
        """
        if not self.settings.get("startup.restore_last", True):
            return False

        last_wallpapers: dict[str, str] = self.settings.get(
            "startup.last_wallpapers", {}
        ) or {}
        if not last_wallpapers:
            # Fallback al último del historial.
            entry = self.history.last()
            if entry is None:
                return False
            try:
                return self.apply(entry.path, monitor=entry.monitor, notify=False)
            except WallpaperManagerError:
                return False

        success = False
        for monitor, path_str in last_wallpapers.items():
            path = Path(path_str)
            if not path.exists():
                logger.warning("Último wallpaper no existe: %s", path)
                continue
            try:
                if self.apply(path, monitor=monitor, notify=False):
                    success = True
            except WallpaperManagerError as exc:
                logger.warning("No se pudo restaurar %s: %s", path, exc)
        logger.info("Restauración de fondos completada (éxito=%s)", success)
        return success

    def _save_last_wallpaper(self, path: Path, monitor: str) -> None:
        """Persiste el último wallpaper aplicado por monitor."""
        last: dict[str, str] = self.settings.get("startup.last_wallpapers", {}) or {}
        last[monitor] = str(path)
        self.settings.set("startup.last_wallpapers", last, autosave=True)

    # ------------------------------------------------------------------ #
    # Rotación automática
    # ------------------------------------------------------------------ #
    def start_rotation(
        self,
        *,
        interval_seconds: int | None = None,
        playlist_id: str | None = None,
        random_order: bool | None = None,
    ) -> bool:
        """Inicia la rotación automática de wallpapers en segundo plano.

        Args:
            interval_seconds: Intervalo entre cambios. Si se omite, usa la
                configuración global.
            playlist_id: ID de playlist a usar. Si se omite, rota entre
                todos los wallpapers de la biblioteca.
            random_order: Si ``True``, orden aleatorio.

        Returns:
            ``True`` si se inició la rotación.
        """
        if self._rotation_thread and self._rotation_thread.is_alive():
            logger.warning("La rotación ya está activa")
            return False

        interval = interval_seconds or int(
            self.settings.get("rotation.interval_seconds", 1800)
        )
        interval = max(10, interval)
        random_order = (
            random_order
            if random_order is not None
            else bool(self.settings.get("rotation.random_order", False))
        )

        playlist = None
        if playlist_id:
            playlist = self.playlists.get(playlist_id)
            if not playlist:
                logger.error("Playlist no encontrada: %s", playlist_id)
                return False

        self._rotation_stop.clear()
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop,
            args=(interval, playlist, random_order),
            daemon=True,
            name="wallpaper-rotation",
        )
        self._rotation_thread.start()
        self.settings.set("rotation.enabled", True, autosave=True)
        self._emit("rotation_started", {"interval": interval, "playlist_id": playlist_id})
        logger.info("Rotation started (interval=%ds, random=%s)", interval, random_order)
        return True

    def stop_rotation(self) -> bool:
        """Detiene la rotación automática."""
        if not self._rotation_thread:
            return False
        self._rotation_stop.set()
        if self._rotation_thread.is_alive():
            self._rotation_thread.join(timeout=2.0)
        self._rotation_thread = None
        self.settings.set("rotation.enabled", False, autosave=True)
        self._emit("rotation_stopped", {})
        logger.info("Rotation stopped")
        return True

    @property
    def is_rotating(self) -> bool:
        """Indica si la rotación está activa."""
        return bool(self._rotation_thread and self._rotation_thread.is_alive())

    def _rotation_loop(
        self,
        interval: int,
        playlist,
        random_order: bool,
    ) -> None:
        """Bucle de rotación ejecutado en un hilo aparte."""
        index = 0
        while not self._rotation_stop.is_set():
            items: list[Path] = []
            if playlist:
                items = playlist.paths()
            else:
                items = [item.path for item in self.library.items]
            if not items:
                logger.warning("No wallpapers to rotate")
                self._rotation_stop.wait(interval)
                continue

            if random_order:
                target = random.choice(items)
            else:
                target = items[index % len(items)]
                index += 1

            try:
                self.apply(target, notify=False)
            except WallpaperManagerError as exc:
                logger.warning("No se pudo aplicar %s en rotación: %s", target, exc)

            # Esperar el intervalo (interrumpible).
            if self._rotation_stop.wait(interval):
                break

    # ------------------------------------------------------------------ #
    # Autoinicio con Hyprland
    # ------------------------------------------------------------------ #
    def enable_autostart(self) -> bool:
        """Habilita el inicio automático de la app con Hyprland."""
        exec_line = "frostwall"
        success = self.hyprland.enable_autostart(exec_line)
        if success:
            self.settings.set("startup.auto_start", True, autosave=True)
            self.notifier.info("Autostart enabled", "Frostwall will start with Hyprland")
        return success

    def disable_autostart(self) -> bool:
        """Deshabilita el inicio automático."""
        exec_line = "frostwall"
        success = self.hyprland.disable_autostart(exec_line)
        if success:
            self.settings.set("startup.auto_start", False, autosave=True)
        return success

    # ------------------------------------------------------------------ #
    # Monitor de foco/inactividad
    # ------------------------------------------------------------------ #
    def start_focus_monitor(self) -> None:
        """Crea e inicia el monitor de foco/inactividad si alguna función
        de pausa está habilitada."""
        if self.focus_monitor is None:
            self.focus_monitor = FocusMonitor(
                self.hyprland, self.mpvpaper, settings=self.settings
            )
        if self._focus_monitor_should_run():
            self.focus_monitor.start()

    def reconfigure_focus_monitor(self) -> None:
        """Aplica la configuración actual al monitor de foco/inactividad.

        Arranca o detiene el temporizador según las opciones de pausa. Las
        opciones finer-grained (minutos de inactividad) se leen en vivo.
        """
        if self.focus_monitor is None:
            self.start_focus_monitor()
            return
        if self._focus_monitor_should_run():
            self.focus_monitor.start()
        else:
            self.focus_monitor.stop()

    def _focus_monitor_should_run(self) -> bool:
        return bool(
            self.settings.get("mpvpaper.pause_on_focus_loss", True)
        ) or bool(self.settings.get("mpvpaper.idle_pause_enabled", False))

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    def _default_monitor_name(self) -> str:
        """Devuelve el nombre del monitor por defecto."""
        configured = self.settings.get("hyprland.default_monitor", "")
        if configured:
            return configured
        primary = self.monitors.get_primary()
        if primary:
            return primary.name
        monitors = self.monitors.refresh()
        return monitors[0].name if monitors else ""

    def refresh_monitors(self) -> list:
        """Refresca la lista de monitores detectados."""
        return self.monitors.refresh()

    def cleanup(self) -> None:
        """Limpia recursos antes de cerrar la aplicación."""
        self.stop_rotation()
        if self.focus_monitor is not None:
            self.focus_monitor.stop()
        self.library.stop_watching()
        logger.info("WallpaperManager detenido")
