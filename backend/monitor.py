"""
Monitor
=======

Modelo de monitor y gestor de monitores para Hyprland.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.hyprland import Hyprland

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Monitor:
    """Representa un monitor conectado a Hyprland.

    Attributes:
        id: Identificador numérico de Hyprland.
        name: Nombre (por ejemplo ``"DP-1"``).
        description: Descripción legible.
        width: Ancho en píxeles.
        height: Alto en píxeles.
        refresh_rate: Tasa de refresco en Hz.
        scale: Escala actual.
        transform: Transformación aplicada (rotación / espejo).
        focused: Si tiene el foco actualmente.
        primary: Si se considera primario.
    """

    id: int
    name: str
    description: str = ""
    width: int = 0
    height: int = 0
    refresh_rate: float = 0.0
    scale: float = 1.0
    transform: int = 0
    focused: bool = False
    primary: bool = False
    available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resolution(self) -> str:
        """Resolución legible (por ejemplo ``"1920x1080"``)."""
        return f"{self.width}x{self.height}"

    @property
    def aspect_ratio(self) -> float:
        """Relación de aspecto (ancho/alto)."""
        return (self.width / self.height) if self.height else 0.0

    @classmethod
    def from_hyprctl(cls, data: dict[str, Any]) -> "Monitor":
        """Crea un :class:`Monitor` a partir del JSON de ``hyprctl monitors``."""
        return cls(
            id=int(data.get("id", 0)),
            name=str(data.get("name", "unknown")),
            description=str(data.get("description", "")),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            refresh_rate=float(data.get("refreshRate", 0.0) or 0.0),
            scale=float(data.get("scale", 1.0) or 1.0),
            transform=int(data.get("transform", 0) or 0),
            focused=bool(data.get("focused", False)),
            available=bool(data.get("available", True)),
            primary=bool(data.get("focused", False)),
            metadata=data,
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.resolution}@{self.refresh_rate:.0f}Hz)"


class MonitorManager:
    """Gestiona la lista de monitores conectados.

    Cachea la última consulta a ``hyprctl`` y permite refrescarla.
    """

    def __init__(self, hyprland: Hyprland | None = None) -> None:
        self._hyprland = hyprland or Hyprland()
        self._monitors: list[Monitor] = []
        self.refresh()

    def refresh(self) -> list[Monitor]:
        """Refresca la lista de monitores desde Hyprland.

        Returns:
            Lista actualizada de monitores.
        """
        try:
            raw = self._hyprland.list_monitors()
        except Exception:  # noqa: BLE001
            logger.exception("Error al listar monitores")
            self._monitors = []
            return self._monitors

        monitors = [Monitor.from_hyprctl(item) for item in raw]
        # Ordenar por ID para un orden estable.
        monitors.sort(key=lambda m: m.id)
        self._monitors = monitors
        logger.debug("Detectados %d monitores", len(monitors))
        return monitors

    @property
    def monitors(self) -> list[Monitor]:
        """Lista de monitores (caché)."""
        return list(self._monitors)

    def get_by_name(self, name: str) -> Monitor | None:
        """Busca un monitor por nombre.

        Args:
            name: Nombre del monitor (por ejemplo ``"DP-1"``).

        Returns:
            Monitor encontrado o ``None``.
        """
        for monitor in self._monitors:
            if monitor.name == name:
                return monitor
        return None

    def get_primary(self) -> Monitor | None:
        """Devuelve el monitor primario (con foco)."""
        for monitor in self._monitors:
            if monitor.focused:
                return monitor
        return self._monitors[0] if self._monitors else None

    def names(self) -> list[str]:
        """Lista de nombres de monitores."""
        return [m.name for m in self._monitors]

    def __len__(self) -> int:
        return len(self._monitors)

    def __iter__(self):
        return iter(self._monitors)
