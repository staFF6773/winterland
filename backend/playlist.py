"""
Playlist
========

Listas de reproducción de wallpapers.

Una playlist es una secuencia ordenada de wallpapers que pueden
rotarse automáticamente. Las listas se persisten en JSON.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterable, Iterator
from uuid import uuid4

from utils.file_utils import expand

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PlaylistEntry:
    """Entrada individual de una playlist.

    Attributes:
        path: Ruta del wallpaper.
        order: Orden dentro de la playlist (0-based).
    """

    path: str
    order: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PlaylistEntry":
        return cls(
            path=str(data.get("path", "")),
            order=int(data.get("order", 0)),
        )


@dataclass(slots=True)
class Playlist:
    """Lista de reproducción de wallpapers.

    Attributes:
        id: Identificador único.
        name: Nombre legible.
        entries: Lista de entradas ordenadas.
        created_at: Fecha de creación.
        shuffle: Si ``True``, reproduce en orden aleatorio.
        interval_seconds: Intervalo de rotación por defecto.
    """

    name: str
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    entries: list[PlaylistEntry] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    shuffle: bool = False
    interval_seconds: int = 1800

    def add(self, path: Path | str) -> None:
        """Añade un wallpaper al final de la playlist."""
        order = len(self.entries)
        self.entries.append(PlaylistEntry(path=str(expand(path).resolve()), order=order))

    def remove(self, path: Path | str) -> bool:
        """Elimina un wallpaper de la playlist."""
        target = str(expand(path).resolve())
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.path != target]
        # Reordenar.
        for idx, entry in enumerate(self.entries):
            entry.order = idx
        return len(self.entries) < before

    def reorder(self, from_idx: int, to_idx: int) -> None:
        """Mueve una entrada de posición."""
        if not (0 <= from_idx < len(self.entries)):
            return
        if not (0 <= to_idx < len(self.entries)):
            return
        entry = self.entries.pop(from_idx)
        self.entries.insert(to_idx, entry)
        for idx, e in enumerate(self.entries):
            e.order = idx

    def paths(self) -> list[Path]:
        """Devuelve las rutas en orden."""
        return [Path(e.path) for e in self.entries]

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[PlaylistEntry]:
        return iter(self.entries)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at,
            "shuffle": self.shuffle,
            "interval_seconds": self.interval_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Playlist":
        return cls(
            name=str(data.get("name", "Sin nombre")),
            id=str(data.get("id", uuid4().hex[:12])),
            entries=[PlaylistEntry.from_dict(e) for e in data.get("entries", [])],
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            shuffle=bool(data.get("shuffle", False)),
            interval_seconds=int(data.get("interval_seconds", 1800)),
        )


class PlaylistManager:
    """Gestiona múltiples playlists con persistencia JSON.

    Attributes:
        path: Ruta del archivo de persistencia.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path = (
            expand(path)
            if path
            else Path.home() / ".config/frostwall/playlists.json"
        )
        self._lock = RLock()
        self._playlists: dict[str, Playlist] = {}
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
            for item in data:
                if isinstance(item, dict):
                    playlist = Playlist.from_dict(item)
                    self._playlists[playlist.id] = playlist
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Error loading playlists: %s", exc)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(
                    [p.to_dict() for p in self._playlists.values()],
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
            tmp.replace(self.path)
        except OSError as exc:
            logger.error("Could not save playlists: %s", exc)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def create(self, name: str) -> Playlist:
        """Crea una nueva playlist vacía."""
        playlist = Playlist(name=name)
        with self._lock:
            self._playlists[playlist.id] = playlist
            self._save()
        logger.info("Playlist created: %s (%s)", playlist.name, playlist.id)
        return playlist

    def delete(self, playlist_id: str) -> bool:
        """Elimina una playlist por ID."""
        with self._lock:
            if playlist_id not in self._playlists:
                return False
            del self._playlists[playlist_id]
            self._save()
        return True

    def get(self, playlist_id: str) -> Playlist | None:
        """Obtiene una playlist por ID."""
        with self._lock:
            return self._playlists.get(playlist_id)

    def find_by_name(self, name: str) -> Playlist | None:
        """Busca la primera playlist con ese nombre."""
        with self._lock:
            for playlist in self._playlists.values():
                if playlist.name == name:
                    return playlist
        return None

    def all(self) -> list[Playlist]:
        """Devuelve todas las playlists."""
        with self._lock:
            return list(self._playlists.values())

    def add_to(self, playlist_id: str, path: Path | str) -> bool:
        """Añade un wallpaper a una playlist existente."""
        with self._lock:
            playlist = self._playlists.get(playlist_id)
            if playlist is None:
                return False
            playlist.add(path)
            self._save()
        return True

    def remove_from(self, playlist_id: str, path: Path | str) -> bool:
        """Elimina un wallpaper de una playlist."""
        with self._lock:
            playlist = self._playlists.get(playlist_id)
            if playlist is None:
                return False
            removed = playlist.remove(path)
            if removed:
                self._save()
        return removed

    def __iter__(self) -> Iterator[Playlist]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._playlists)
