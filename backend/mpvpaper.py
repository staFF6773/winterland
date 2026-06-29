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
        self._cached_monitor: str | None = None  # monitor destino cacheado

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    def is_running(self, monitor: str | None = None) -> bool:
        """Indica si mpvpaper está corriendo (en un monitor concreto).

        Usa una comprobación barata de vida del PID rastreado y sólo cae
        en un escaneo completo de la tabla de procesos cuando no hay PIDs
        rastreados (p. ej. mpvpaper lanzado externamente); en ese caso
        adopta los PIDs encontrados para que las siguientes comprobaciones
        vuelvan a ser baratas.
        """
        self._reap_dead_tracked()
        if monitor is not None:
            return monitor in self._current_processes
        if self._current_processes:
            return True
        # Sin PIDs rastreados: escaneo completo y adopción (mpvpaper externo).
        self._adopt_external_processes()
        return bool(self._current_processes)

    def _adopt_external_processes(self) -> None:
        """Detecta mpvpaper lanzado externamente y lo rastrea por monitor."""
        for pid, cmdline in self._find_processes():
            monitor = self._monitor_from_cmdline(cmdline)
            if monitor and monitor not in self._current_processes and self._pid_alive(pid):
                self._current_processes[monitor] = pid

    @staticmethod
    def _monitor_from_cmdline(cmdline: list[str]) -> str:
        """Extrae el nombre del monitor desde la línea de comandos de mpvpaper."""
        for token in cmdline[1:]:
            if token.startswith("-") or "/" in token:
                continue
            return token
        return ""

    def _pid_alive(self, pid: int) -> bool:
        """Comprueba si un PID sigue vivo (barato, sin escanear la tabla)."""
        try:
            return bool(psutil.pid_exists(pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _reap_dead_tracked(self) -> None:
        """Elimina los PIDs rastreados que ya no existen."""
        dead = [m for m, pid in self._current_processes.items() if not self._pid_alive(pid)]
        for m in dead:
            self._current_processes.pop(m, None)

    def _tracked_pid_for(self, monitor: str | None) -> int | None:
        """Devuelve el PID rastreado para un monitor (o el primero)."""
        self._reap_dead_tracked()
        if monitor is not None:
            return self._current_processes.get(monitor)
        if self._current_processes:
            return next(iter(self._current_processes.values()))
        return None

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
        max_fps: int | None = None,
    ) -> bool:
        """Reproduce un vídeo/GIF animado como fondo.

        Args:
            video_path: Ruta del archivo multimedia.
            monitor: Monitor destino (vacío = primario).
            loop: Si ``True``, reproduce en bucle.
            mute: Si ``True``, silencia el audio.
            mpv_options: Opciones MPV (anula las del constructor si se da).
            max_fps: Si se establece, limita los fps de salida vía filtro
                ``lavfi=[fps=N]`` (sin pérdida de calidad de imagen, sólo
                reduce la suavidad de movimiento para ahorrar CPU/GPU).

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
        if max_fps and max_fps > 0 and "--vf=" not in opts and "--vf " not in opts:
            opts += f" --vf=lavfi=[fps={int(max_fps)}]"

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
        self._cached_monitor = target_monitor
        return True

    def stop(self, monitor: str | None = None) -> bool:
        """Detiene mpvpaper (en un monitor concreto o en todos).

        Args:
            monitor: Monitor a detener. ``None`` detiene todas las instancias.

        Returns:
            ``True`` si se detuvo al menos un proceso.
        """
        stopped = False
        # Vía rápida: PID rastreado para un monitor concreto.
        if monitor is not None:
            pid = self._current_processes.get(monitor)
            if pid is not None and self._pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    stopped = True
                except (ProcessLookupError, PermissionError):
                    pass
            self._current_processes.pop(monitor, None)
            if monitor == self._cached_monitor:
                self._cached_monitor = None
            if stopped:
                logger.info("mpvpaper stopped on %s", monitor)
                return stopped

        # Vía lenta: escaneo completo (detener todo o instancias externas).
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
        self._cached_monitor = None
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
        self._reap_dead_tracked()
        if monitor:
            pid = self._current_processes.get(monitor)
            if pid is not None:
                return {"running": True, "monitor": monitor, "pid": pid}
        elif self._current_processes:
            m, pid = next(iter(self._current_processes.items()))
            return {"running": True, "monitor": m, "pid": pid}

        # Fallback: escaneo completo (mpvpaper externo o PIDs caducados).
        processes = self._find_processes()
        if not processes:
            return {"running": False}
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
        target = monitor or self._cached_monitor or self._default_monitor()
        if monitor is None and target:
            # Cachea el monitor resuelto para evitar llamadas a hyprctl.
            self._cached_monitor = target
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
        pid = self._tracked_pid_for(monitor)
        pids = [pid] if pid else [p for p, _ in self._find_processes()]
        for pid in pids:
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
        pid = self._tracked_pid_for(monitor)
        pids = [pid] if pid else [p for p, _ in self._find_processes()]
        for pid in pids:
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
