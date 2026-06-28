"""
Hyprland
========

Integración con el compositor Hyprland mediante :command:`hyprctl`.

Proporciona utilidades para detectar monitores, ejecutar comandos y
obtener información del compositor.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HyprlandVersion:
    """Versión del compositor Hyprland."""

    tag: str
    commit: str
    date: str

    def __str__(self) -> str:
        return f"{self.tag} ({self.commit[:7]})"


class Hyprland:
    """Cliente de :command:`hyprctl`.

    Attributes:
        hyprctl_path: Ruta al binario ``hyprctl``.
    """

    def __init__(self, hyprctl_path: str | None = None) -> None:
        """Inicializa el cliente.

        Args:
            hyprctl_path: Ruta al binario ``hyprctl``. Si se omite se busca
                en ``PATH``.
        """
        self.hyprctl_path: str = hyprctl_path or self._find_hyprctl()
        self._instance_signature: str | None = None

    # ------------------------------------------------------------------ #
    # Utilidades estáticas
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_hyprctl() -> str:
        """Localiza ``hyprctl`` en el ``PATH``."""
        from shutil import which

        path = which("hyprctl") or "/usr/bin/hyprctl"
        return path

    @staticmethod
    def is_available() -> bool:
        """Indica si Hyprland está en ejecución.

        Comprueba la variable ``HYPRLAND_INSTANCE_SIGNATURE`` y la
        disponibilidad de ``hyprctl``.
        """
        if "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ:
            return False
        from shutil import which

        return which("hyprctl") is not None

    @property
    def instance_signature(self) -> str | None:
        """Devuelve la firma de instancia actual de Hyprland."""
        if self._instance_signature is None:
            self._instance_signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        return self._instance_signature

    # ------------------------------------------------------------------ #
    # Ejecución de comandos
    # ------------------------------------------------------------------ #
    def run(self, *args: str, timeout: float = 5.0) -> str:
        """Ejecuta ``hyprctl`` con los argumentos dados.

        Args:
            *args: Argumentos pasados a ``hyprctl``.
            timeout: Tiempo máximo de espera.

        Returns:
            Salida estándar decodificada.

        Raises:
            RuntimeError: Si la llamada falla.
        """
        cmd = [self.hyprctl_path, *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"hyprctl no encontrado: {self.hyprctl_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"hyprctl superó el tiempo de espera: {args}") from exc

        if result.returncode != 0:
            err = result.stderr.strip()
            raise RuntimeError(f"hyprctl falló ({result.returncode}): {err}")
        return result.stdout

    def run_json(self, *args: str, timeout: float = 5.0) -> Any:
        """Ejecuta ``hyprctl -j`` y parsea la salida como JSON.

        Args:
            *args: Argumentos para ``hyprctl``.
            timeout: Tiempo máximo de espera.

        Returns:
            Objeto JSON decodificado (lista o dict).
        """
        output = self.run("-j", *args, timeout=timeout)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON response from hyprctl: %s", output[:200])
            raise RuntimeError(f"hyprctl devolvió JSON inválido: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Monitores
    # ------------------------------------------------------------------ #
    def list_monitors(self) -> list[dict[str, Any]]:
        """Devuelve la lista de monitores conectados.

        Returns:
            Lista de diccionarios con la información de cada monitor.
        """
        try:
            data = self.run_json("monitors")
            if isinstance(data, list):
                return data
            logger.warning("Unexpected hyprctl monitors output: %r", data)
            return []
        except RuntimeError as exc:
            logger.error("Could not list monitors: %s", exc)
            return []

    def get_active_monitor(self) -> dict[str, Any] | None:
        """Devuelve el monitor donde está el foco actual."""
        for monitor in self.list_monitors():
            if monitor.get("focused"):
                return monitor
        return None

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    def dispatch(self, command: str, *args: str) -> str:
        """Ejecuta ``hyprctl dispatch <command> <args>``."""
        return self.run("dispatch", command, *args)

    def reload_config(self) -> str:
        """Recarga la configuración de Hyprland."""
        return self.run("reload")

    def notify(
        self,
        message: str,
        *,
        icon: int = 0,
        timeout_ms: int = 4000,
        color: int = 0xFFFFFFFF,
    ) -> str:
        """Muestra una notificación nativa de Hyprland.

        Args:
            message: Texto a mostrar.
            icon: ID de icono Hyprland (0 = sin icono).
            timeout_ms: Duración en milisegundos.
            color: Color ARGB.

        Returns:
            Respuesta de ``hyprctl``.
        """
        return self.run(
            "notify",
            str(icon),
            str(timeout_ms),
            str(color),
            message,
        )

    def get_version(self) -> HyprlandVersion | None:
        """Devuelve información de versión de Hyprland."""
        try:
            data = self.run_json("version")
        except RuntimeError:
            return None
        if not isinstance(data, dict):
            return None
        return HyprlandVersion(
            tag=str(data.get("tag", "unknown")).lstrip("v"),
            commit=str(data.get("commit", "")),
            date=str(data.get("date", "")),
        )

    # ------------------------------------------------------------------ #
    # Autoinicio
    # ------------------------------------------------------------------ #
    @staticmethod
    def autostart_config_path() -> Path:
        """Devuelve la ruta del archivo de configuración de Hyprland."""
        return Path(os.path.expanduser("~/.config/hypr/hyprland.conf"))

    def enable_autostart(self, exec_line: str) -> bool:
        """Añade una línea ``exec-once`` a la configuración de Hyprland.

        Args:
            exec_line: Comando a ejecutar al inicio.

        Returns:
            ``True`` si se modificó el archivo.
        """
        config_path = self.autostart_config_path()
        if not config_path.exists():
            logger.warning("%s does not exist; cannot configure autostart", config_path)
            return False

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Could not read %s: %s", config_path, exc)
            return False

        marker = f"exec-once = {exec_line}"
        if marker in content:
            logger.info("Autostart already present in hyprland.conf")
            return True

        # Añadir al final con un comentario.
        addition = f"\n# Frostwall autostart\n{marker}\n"
        try:
            config_path.write_text(content + addition, encoding="utf-8")
            logger.info("Autostart added to %s", config_path)
            return True
        except OSError as exc:
            logger.error("Could not write %s: %s", config_path, exc)
            return False

    def disable_autostart(self, exec_line: str) -> bool:
        """Elimina la línea de autostart indicada.

        Args:
            exec_line: Comando a retirar.

        Returns:
            ``True`` si se modificó el archivo.
        """
        config_path = self.autostart_config_path()
        if not config_path.exists():
            return False
        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError:
            return False

        marker = f"exec-once = {exec_line}"
        if marker not in content:
            return False

        new_lines = [
            line for line in content.splitlines()
            if line.strip() != marker
            and line.strip() != "# Wallpaper Manager autostart"
            and line.strip() != "# Frostwall autostart"
        ]
        try:
            config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True
        except OSError as exc:
            logger.error("No se pudo escribir %s: %s", config_path, exc)
            return False
