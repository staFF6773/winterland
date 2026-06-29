"""
Mpvpaper
========

Control de :command:`mpvpaper` para fondos animados.

Mpvpaper es un fondo de pantalla animado basado en mpv para Wayland.
Esta clase gestiona su ciclo de vida, los controles de reproducción y
la selección de monitor.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from utils.file_utils import expand, is_animated
from backend.hyprland import Hyprland

logger = logging.getLogger(__name__)


class MpvpaperError(RuntimeError):
    """Error en operaciones de mpvpaper."""


class Mpvpaper:
    """Gestiona :command:`mpvpaper` para fondos animados.

    Attributes:
        executable: Ruta al binario ``mpvpaper``.
        mpv_options: Opciones pasadas a mpv (por ejemplo ``--loop-file``).
        hyprland: Cliente Hyprland asociado.
    """

    def __init__(
        self,
        *,
        executable: str = "mpvpaper",
        mpv_options: str = "--no-audio --loop-file --panscan=1.0 --hwdec=auto-safe --framedrop=vo --sws-fast=yes",
        hyprland: Hyprland | None = None,
    ) -> None:
        self.executable = executable
        self.mpv_options = mpv_options
        self.hyprland = hyprland or Hyprland()
        self._current_processes: dict[str, int] = {}  # monitor -> PID

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    def is_running(self, monitor: str | None = None) -> bool:
        """Indica si mpvpaper está corriendo (en un monitor concreto)."""
        processes = self._find_processes()
        if monitor is None:
            return len(processes) > 0
        return any(monitor in args for _, args in processes)

    def _find_processes(self) -> list[tuple[int, list[str]]]:
        """Lista procesos mpvpaper con su línea de comandos."""
        result: list[tuple[int, list[str]]] = []
        try:
            procs = list(psutil.process_iter(["pid", "name", "cmdline"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return result
        for proc in procs:
            try:
                name = proc.info.get("name") or ""
                if "mpvpaper" not in name:
                    continue
                cmdline = proc.info.get("cmdline") or []
                result.append((proc.info["pid"], list(cmdline)))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return result

    # ------------------------------------------------------------------ #
    # Reproducción
    # ------------------------------------------------------------------ #
    def play(
        self,
        video_path: Path | str,
        monitor: str = "",
        *,
        loop: bool = True,
        mute: bool = True,
        mpv_options: str | None = None,
    ) -> bool:
        """Reproduce un vídeo/GIF animado como fondo.

        Args:
            video_path: Ruta del archivo multimedia.
            monitor: Monitor destino (vacío = primario).
            loop: Si ``True``, reproduce en bucle.
            mute: Si ``True``, silencia el audio.
            mpv_options: Opciones MPV (anula las del constructor si se da).

        Returns:
            ``True`` si se inició la reproducción.

        Raises:
            MpvpaperError: Si el archivo no es válido o mpvpaper falta.
        """
        path = expand(video_path)
        if not path.exists():
            raise MpvpaperError(f"El archivo no existe: {path}")

        if not self._which(self.executable):
            raise MpvpaperError(f"Ejecutable no encontrado: {self.executable}")

        # Detener cualquier instancia previa en el mismo monitor.
        target_monitor = monitor or self._default_monitor()
        if not target_monitor:
            raise MpvpaperError("No se detectó ningún monitor destino")

        self.stop(target_monitor)

        opts = mpv_options if mpv_options is not None else self.mpv_options
        if loop and "--loop-file" not in opts:
            opts += " --loop-file"
        if mute and "--no-audio" not in opts:
            opts += " --no-audio"

        cmd = [self.executable, target_monitor, opts, str(path)]
        logger.info("Starting mpvpaper on %s: %s", target_monitor, path.name)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise MpvpaperError(f"No se pudo iniciar mpvpaper: {exc}") from exc

        self._current_processes[target_monitor] = proc.pid
        return True

    def stop(self, monitor: str | None = None) -> bool:
        """Detiene mpvpaper (en un monitor concreto o en todos).

        Args:
            monitor: Monitor a detener. ``None`` detiene todas las instancias.

        Returns:
            ``True`` si se detuvo al menos un proceso.
        """
        stopped = False
        for pid, cmdline in self._find_processes():
            if monitor is not None and monitor not in " ".join(cmdline):
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                stopped = True
            except (ProcessLookupError, PermissionError):
                continue
        if monitor and monitor in self._current_processes:
            self._current_processes.pop(monitor, None)
        if stopped:
            logger.info("mpvpaper stopped on %s", monitor or "all")
        return stopped

    # ------------------------------------------------------------------ #
    # Controles de reproducción vía socket IPC de mpv
    # ------------------------------------------------------------------ #
    def pause(self, monitor: str | None = None) -> bool:
        """Pausa la reproducción."""
        return self._send_mpv_command(["set", "pause", "yes"], monitor)

    def resume(self, monitor: str | None = None) -> bool:
        """Reanuda la reproducción."""
        return self._send_mpv_command(["set", "pause", "no"], monitor)

    def play_pause(self, monitor: str | None = None) -> bool:
        """Alterna entre reproducción y pausa."""
        return self._send_mpv_command(["cycle", "pause"], monitor)

    def restart(self, monitor: str | None = None) -> bool:
        """Reinicia la reproducción desde el inicio."""
        return self._send_mpv_command(["seek", "0", "absolute"], monitor)

    def seek(self, seconds: float, monitor: str | None = None) -> bool:
        """Avanza o retrocede ``seconds`` segundos."""
        return self._send_mpv_command(["seek", str(seconds), "relative"], monitor)

    def set_volume(self, volume: int, monitor: str | None = None) -> bool:
        """Establece el volumen (0-100)."""
        volume = max(0, min(100, volume))
        return self._send_mpv_command(["set", "volume", str(volume)], monitor)

    def set_speed(self, speed: float, monitor: str | None = None) -> bool:
        """Establece la velocidad de reproducción (0.25-4.0)."""
        speed = max(0.25, min(4.0, speed))
        return self._send_mpv_command(["set", "speed", str(speed)], monitor)

    # ------------------------------------------------------------------ #
    # Información
    # ------------------------------------------------------------------ #
    def get_state(self, monitor: str | None = None) -> dict[str, Any]:
        """Devuelve el estado actual de reproducción.

        Returns:
            Diccionario con ``running``, ``monitor``, ``pid``.
        """
        processes = self._find_processes()
        if not processes:
            return {"running": False}
        if monitor:
            for pid, cmdline in processes:
                if monitor in " ".join(cmdline):
                    return {"running": True, "monitor": monitor, "pid": pid}
        pid, cmdline = processes[0]
        return {"running": True, "monitor": monitor or "default", "pid": pid}

    # ------------------------------------------------------------------ #
    # Privados
    # ------------------------------------------------------------------ #
    def _default_monitor(self) -> str:
        """Obtiene el monitor primario detectado."""
        try:
            monitors = self.hyprland.list_monitors()
            for m in monitors:
                if m.get("focused"):
                    return str(m.get("name", ""))
            if monitors:
                return str(monitors[0].get("name", ""))
        except Exception:  # noqa: BLE001
            logger.debug("No se pudo obtener monitor primario")
        return ""

    def _send_mpv_command(self, command: list[str], monitor: str | None) -> bool:
        """Envía un comando IPC a mpvpaper.

        Mpvpaper expone un socket JSON IPC por monitor en
        ``/tmp/mpvpaper-<monitor>``. Si el socket no está disponible,
        se simula el comando vía señales Unix (sólo pausa/reanudación).
        """
        target = monitor or self._default_monitor()
        socket_path = f"/tmp/mpvpaper-{target}"

        # Intentar IPC por socket.
        try:
            import json
            import socket as sock

            client = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(socket_path)
            payload = json.dumps({"command": command}) + "\n"
            client.sendall(payload.encode("utf-8"))
            client.close()
            return True
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            # Fallback: pausa/reanudación mediante SIGSTOP / SIGCONT.
            if command[:3] == ["set", "pause", "yes"]:
                return self._pause_via_signal(target, pause=True)
            if command[:3] == ["set", "pause", "no"]:
                return self._pause_via_signal(target, pause=False)
            if command[:2] == ["cycle", "pause"]:
                return self._toggle_pause_via_signal(target)
            logger.warning("No se pudo enviar comando IPC a mpvpaper en %s", target)
            return False

    def _pause_via_signal(self, monitor: str, *, pause: bool) -> bool:
        """Pausa o reanuda mpv mediante señales Unix (fallback)."""
        for pid, _ in self._find_processes():
            try:
                os.kill(pid, signal.SIGSTOP if pause else signal.SIGCONT)
                return True
            except (ProcessLookupError, PermissionError):
                continue
        return False

    def _toggle_pause_via_signal(self, monitor: str) -> bool:
        """Alterna pausa mediante señales Unix (fallback).

        Nota: esto es una aproximación; el IPC es el método recomendado.
        """
        for pid, _ in self._find_processes():
            try:
                proc = psutil.Process(pid)
                if proc.status() == psutil.STATUS_STOPPED:
                    os.kill(pid, signal.SIGCONT)
                else:
                    os.kill(pid, signal.SIGSTOP)
                return True
            except (psutil.NoSuchProcess, PermissionError):
                continue
        return False

    @staticmethod
    def _which(name: str) -> str | None:
        from shutil import which

        return which(name)
