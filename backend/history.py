"""
History
=======

Historial de wallpapers aplicados, con persistencia JSON.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterable, Iterator

from utils.file_utils import expand

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HistoryEntry:
    """Entrada del historial de wallpapers.

    Attributes:
        path: Ruta del wallpaper aplicado.
        monitor: Monitor donde se aplicó (vacío = todos).
        applied_at: Marca temporal de aplicación.
        type: Tipo de wallpaper (image / video / gif…).
    """

    path: str
    monitor: str = ""
    applied_at: str = field(default_factory=lambda: datetime.now().isoformat())
    type: str = "image"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "HistoryEntry":
        return cls(
            path=str(data.get("path", "")),
            monitor=str(data.get("monitor", "")),
            applied_at=str(data.get("applied_at", datetime.now().isoformat())),
            type=str(data.get("type", "image")),
        )


class History:
    """Historial circular de wallpapers aplicados.

    Attributes:
        path: Ruta del archivo de persistencia.
        max_entries: Número máximo de entradas retenidas.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        max_entries: int = 100,
    ) -> None:
        """Inicializa el historial.

        Args:
            path: Ruta del archivo JSON. Si se omite se usa
                ``~/.config/wallpaper-manager/history.json``.
            max_entries: Número máximo de entradas (las más recientes primero).
        """
        self.path: Path = (
            expand(path)
            if path
            else Path.home() / ".config/frostwall/history.json"
        )
        self.max_entries = max(10, max_entries)
        self._lock = RLock()
        self._entries: deque[HistoryEntry] = deque(maxlen=self.max_entries)
        self._load()

    # ------------------------------------------------------------------ #
    # Carga / guardado
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                return
            entries = [HistoryEntry.from_dict(item) for item in data if isinstance(item, dict)]
            # Mantener orden cronológico (antiguos -> recientes).
            self._entries = deque(entries, maxlen=self.max_entries)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Error loading history: %s", exc)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(
                    [e.to_dict() for e in self._entries],
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
            tmp.replace(self.path)
        except OSError as exc:
            logger.error("Could not save history: %s", exc)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def add(self, path: Path | str, *, monitor: str = "", type_: str = "image") -> None:
        """Añade una entrada al historial.

        Args:
            path: Ruta del wallpaper aplicado.
            monitor: Monitor destino.
            type_: Tipo de wallpaper.
        """
        entry = HistoryEntry(
            path=str(expand(path).resolve()),
            monitor=monitor,
            type=type_,
        )
        with self._lock:
            # Evitar duplicados consecutivos.
            if self._entries and self._entries[-1].path == entry.path and \
               self._entries[-1].monitor == entry.monitor:
                self._entries[-1] = entry
            else:
                self._entries.append(entry)
            self._save()

    def recent(self, limit: int = 20) -> list[HistoryEntry]:
        """Devuelve las ``limit`` entradas más recientes."""
        with self._lock:
            items = list(self._entries)
        items.reverse()
        return items[:limit]

    def last(self, monitor: str | None = None) -> HistoryEntry | None:
        """Devuelve la última entrada (opcionalmente por monitor)."""
        items = self.recent(limit=1)
        if not items:
            return None
        if monitor is not None and items[0].monitor != monitor:
            for entry in self.recent(limit=self.max_entries):
                if entry.monitor == monitor:
                    return entry
            return None
        return items[0]

    def last_per_monitor(self) -> dict[str, HistoryEntry]:
        """Devuelve la última entrada por cada monitor."""
        result: dict[str, HistoryEntry] = {}
        for entry in self.recent(limit=self.max_entries):
            key = entry.monitor or "_global"
            if key not in result:
                result[key] = entry
        return result

    def clear(self) -> None:
        """Vacía el historial."""
        with self._lock:
            self._entries.clear()
            self._save()

    def __iter__(self) -> Iterator[HistoryEntry]:
        return iter(list(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def as_list(self) -> list[HistoryEntry]:
        """Devuelve una lista con todas las entradas (recientes primero)."""
        items = list(self._entries)
        items.reverse()
        return items
