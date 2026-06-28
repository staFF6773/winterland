"""
Hyprpaper
=========

Control de :command:`hyprpaper` para fondos estáticos.

Hyprpaper es el demonio de fondos de pantalla de Hyprland. Se controla
mediante un socket IPC; esta clase envuelve los comandos habituales y
gestiona su ciclo de vida.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

import psutil

from utils.file_utils import expand
from backend.hyprland import Hyprland

logger = logging.getLogger(__name__)


class HyprpaperError(RuntimeError):
    """Error en operaciones de hyprpaper."""


class Hyprpaper:
    """Gestiona el demonio :command:`hyprpaper`.

    Attributes:
        executable: Ruta al binario ``hyprpaper``.
        config_path: Ruta al archivo de configuración de hyprpaper.
        hyprland: Cliente Hyprland asociado.
    """

    def __init__(
        self,
        *,
        executable: str = "hyprpaper",
        config_path: Path | str | None = None,
        hyprland: Hyprland | None = None,
    ) -> None:
        self.executable = executable
        self.config_path: Path = (
            expand(config_path)
            if config_path
            else Path(os.path.expanduser("~/.config/hypr/hyprpaper.conf"))
        )
        self.hyprland = hyprland or Hyprland()

    # ------------------------------------------------------------------ #
    # Estado del proceso
    # ------------------------------------------------------------------ #
    def is_running(self) -> bool:
        """Indica si hyprpaper está en ejecución."""
        try:
            return any(
                "hyprpaper" in (p.info.get("name") or "")
                for p in psutil.process_iter(["name"])
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def start(self) -> bool:
        """Inicia el demonio hyprpaper en segundo plano.

        Returns:
            ``True`` si se inició correctamente o ya estaba corriendo.
        """
        if self.is_running():
            logger.debug("hyprpaper ya estaba en ejecución")
            return True

        if not self._which(self.executable):
            raise HyprpaperError(f"Ejecutable no encontrado: {self.executable}")

        try:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = env.get(
                "XDG_CONFIG_HOME",
                os.path.expanduser("~/.config"),
            )
            subprocess.Popen(
                [self.executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
            logger.info("hyprpaper iniciado")
            return True
        except OSError as exc:
            raise HyprpaperError(f"No se pudo iniciar hyprpaper: {exc}") from exc

    def stop(self) -> bool:
        """Detiene todas las instancias de hyprpaper.

        Returns:
            ``True`` si se detuvo al menos un proceso.
        """
        stopped = 0
        try:
            procs = list(psutil.process_iter(["pid", "name"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        for proc in procs:
            try:
                name = proc.info.get("name") or ""
                if "hyprpaper" not in name:
                    continue
                os.kill(proc.info["pid"], signal.SIGTERM)
                stopped += 1
            except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
                continue
        if stopped:
            logger.info("Detenidas %d instancias de hyprpaper", stopped)
        return stopped > 0

    def restart(self) -> bool:
        """Reinicia el demonio."""
        self.stop()
        import time

        time.sleep(0.5)
        return self.start()

    # ------------------------------------------------------------------ #
    # Aplicar wallpapers
    # ------------------------------------------------------------------ #
    def apply(
        self,
        image_path: Path | str,
        monitor: str = "",
        *,
        preload: bool = True,
        unload_previous: bool = True,
    ) -> bool:
        """Aplica una imagen estática como fondo.

        Args:
            image_path: Ruta de la imagen a aplicar.
            monitor: Nombre del monitor destino (vacío = todos).
            preload: Si ``True``, carga la imagen antes de aplicarla.
            unload_previous: Si ``True``, libera la imagen previa de la
                memoria de hyprpaper.

        Returns:
            ``True`` si se aplicó correctamente.

        Raises:
            HyprpaperError: Si hyprpaper no está disponible.
        """
        path = expand(image_path)
        if not path.exists():
            raise HyprpaperError(f"La imagen no existe: {path}")

        if not self.is_running():
            logger.info("hyprpaper no estaba corriendo; iniciando…")
            if not self.start():
                raise HyprpaperError("No se pudo iniciar hyprpaper")

        target = monitor or ""

        try:
            if preload:
                try:
                    self._ipc(f"preload {path}")
                except HyprpaperError:
                    logger.warning("Could not preload %s (non-critical)", path.name)
            self._ipc(f"wallpaper {target},{path}")
            if unload_previous:
                self._unload_unused(except_path=path)
        except HyprpaperError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HyprpaperError(f"Error applying wallpaper: {exc}") from exc

        logger.info("Wallpaper applied on %s: %s", target or "all", path.name)
        return True

    def preload(self, image_path: Path | str) -> bool:
        """Pre-carga una imagen en hyprpaper sin aplicarla todavía."""
        path = expand(image_path)
        if not path.exists():
            raise HyprpaperError(f"La imagen no existe: {path}")
        self._ipc(f"preload {path}")
        return True

    def unload(self, image_path: Path | str | None = None) -> bool:
        """Libera imágenes de memoria.

        Args:
            image_path: Ruta específica a liberar. ``None`` libera todas.

        Returns:
            ``True`` si la operación se completó.
        """
        if image_path is None:
            self._ipc("unload all")
        else:
            path = expand(image_path)
            self._ipc(f"unload {path}")
        return True

    # ------------------------------------------------------------------ #
    # Configuración
    # ------------------------------------------------------------------ #
    def write_config(self, entries: list[str]) -> None:
        """Sobrescribe ``hyprpaper.conf`` con las entradas dadas.

        Args:
            entries: Lista de líneas de configuración.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(entries) + "\n"
        self.config_path.write_text(content, encoding="utf-8")
        logger.info("Hyprpaper config written to %s", self.config_path)

    # ------------------------------------------------------------------ #
    # Privados
    # ------------------------------------------------------------------ #
    def _monitor_names(self) -> list[str]:
        """Lista de nombres de monitores detectados."""
        try:
            return [m["name"] for m in self.hyprland.list_monitors()]
        except Exception:  # noqa: BLE001
            return []

    def _unload_unused(self, except_path: Path | str) -> None:
        """Libera todas las imágenes excepto ``except_path``."""
        try:
            self._ipc(f"unload unused")
        except HyprpaperError:
            pass

    def _ipc(self, command: str) -> str:
        """Ejecuta un comando IPC contra hyprpaper mediante ``hyprctl hyprpaper``.

        Args:
            command: Comando IPC (por ejemplo ``"preload /path"``).

        Returns:
            Respuesta de hyprpaper.

        Raises:
            HyprpaperError: Si el comando falla.
        """
        try:
            result = subprocess.run(
                ["hyprctl", "hyprpaper", command],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError as exc:
            raise HyprpaperError("hyprctl no encontrado") from exc
        except subprocess.TimeoutExpired as exc:
            raise HyprpaperError("hyprctl hyprpaper agotó el tiempo") from exc

        if result.returncode != 0:
            raise HyprpaperError(
                    f"hyprpaper IPC failed: {result.stderr.strip() or 'unknown error'}"
            )
        return result.stdout

    @staticmethod
    def _which(name: str) -> str | None:
        from shutil import which

        return which(name)
