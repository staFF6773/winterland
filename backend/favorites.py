"""
Favorites
=========

Gestión de wallpapers favoritos con persistencia JSON.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterable

from utils.file_utils import expand

logger = logging.getLogger(__name__)


class Favorites:
    """Conjunto de wallpapers marcados como favoritos.

    Attributes:
        path: Ruta del archivo de persistencia.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        """Inicializa el gestor de favoritos.

        Args:
            path: Ruta del archivo JSON. Si se omite se usa
                ``~/.config/wallpaper-manager/favorites.json``.
        """
        self.path: Path = (
            expand(path)
            if path
            else Path.home() / ".config/frostwall/favorites.json"
        )
        self._lock = RLock()
        self._data: dict[str, dict[str, object]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Carga / guardado
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                self._data = json.load(handle)
            if not isinstance(self._data, dict):
                self._data = {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Error loading favorites: %s", exc)
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            tmp.replace(self.path)
        except OSError as exc:
            logger.error("Could not save favorites: %s", exc)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def add(self, path: Path | str) -> bool:
        """Marca ``path`` como favorito.

        Returns:
            ``True`` si se añadió (no estaba antes).
        """
        key = str(expand(path).resolve())
        with self._lock:
            if key in self._data:
                return False
            self._data[key] = {
                "added_at": datetime.now().isoformat(),
            }
            self._save()
        logger.debug("Added to favorites: %s", key)
        return True

    def remove(self, path: Path | str) -> bool:
        """Desmarca ``path`` como favorito."""
        key = str(expand(path).resolve())
        with self._lock:
            if key not in self._data:
                return False
            del self._data[key]
            self._save()
        logger.debug("Removed from favorites: %s", key)
        return True

    def toggle(self, path: Path | str) -> bool:
        """Alterna el estado de favorito.

        Returns:
            ``True`` si quedó como favorito, ``False`` en caso contrario.
        """
        if self.contains(path):
            self.remove(path)
            return False
        self.add(path)
        return True

    def contains(self, path: Path | str) -> bool:
        """Indica si ``path`` está marcado como favorito."""
        key = str(expand(path).resolve())
        with self._lock:
            return key in self._data

    def list(self) -> list[Path]:
        """Devuelve la lista de rutas favoritas."""
        with self._lock:
            return [Path(k) for k in self._data]

    def clear(self) -> None:
        """Vacía la lista de favoritos."""
        with self._lock:
            self._data.clear()
            self._save()

    def __contains__(self, path: Path | str) -> bool:
        return self.contains(path)

    def __iter__(self) -> Iterable[Path]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self._data)
