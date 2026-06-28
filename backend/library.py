"""
Library
=======

Escaneo y gestión de la biblioteca de wallpapers.

Define el modelo :class:`WallpaperItem`, el enumerado :class:`WallpaperType`
y la clase :class:`Library` que observa una carpeta y expone una lista
filtrable de wallpapers.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator

from utils.file_utils import (
    expand,
    file_hash,
    human_size,
    is_animated,
    is_gif,
    is_image,
    is_video,
)

logger = logging.getLogger(__name__)


class WallpaperType(str, Enum):
    """Tipo de wallpaper."""

    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"
    ANIMATED_GIF = "animated_gif"

    @classmethod
    def from_path(cls, path: Path | str) -> "WallpaperType":
        """Determina el tipo a partir de la extensión y el contenido."""
        if is_gif(path):
            return cls.ANIMATED_GIF if is_animated(path) else cls.GIF
        if is_video(path):
            return cls.VIDEO
        if is_image(path):
            return cls.IMAGE
        raise ValueError(f"Extensión no soportada: {Path(path).suffix}")


@dataclass(slots=True)
class WallpaperItem:
    """Representa un wallpaper en la biblioteca.

    Attributes:
        path: Ruta absoluta del archivo.
        name: Nombre del archivo sin extensión.
        type: Tipo de wallpaper.
        size: Tamaño en bytes.
        modified: Fecha de última modificación.
        sha256: Hash del archivo (calculado bajo demanda).
    """

    path: Path
    name: str
    type: WallpaperType
    size: int = 0
    modified: datetime = field(default_factory=datetime.now)
    sha256: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path | str) -> "WallpaperItem":
        """Crea un :class:`WallpaperItem` leyendo metadatos del archivo."""
        p = expand(path)
        stat = p.stat()
        return cls(
            path=p,
            name=p.stem,
            type=WallpaperType.from_path(p),
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )

    @property
    def human_size(self) -> str:
        """Tamaño legible (por ejemplo ``"1.4 MB"``)."""
        return human_size(self.size)

    @property
    def is_animated(self) -> bool:
        """Indica si el wallpaper es animado."""
        return self.type in (WallpaperType.VIDEO, WallpaperType.ANIMATED_GIF)

    def compute_hash(self) -> str:
        """Calcula y almacena el hash SHA-256 del archivo."""
        self.sha256 = file_hash(self.path)
        return self.sha256

    def __str__(self) -> str:
        return f"{self.name} ({self.type.value})"


class Library:
    """Biblioteca de wallpapers observando una carpeta.

    Attributes:
        folder: Carpeta raíz de wallpapers.
        recursive: Si ``True``, escanea recursivamente.
    """

    SUPPORTED_EXTENSIONS: tuple[str, ...] = (
        ".png", ".jpg", ".jpeg", ".webp", ".bmp",
        ".mp4", ".webm", ".gif",
    )

    def __init__(
        self,
        folder: Path | str,
        *,
        recursive: bool = True,
        image_extensions: Iterable[str] | None = None,
        video_extensions: Iterable[str] | None = None,
    ) -> None:
        """Inicializa la biblioteca.

        Args:
            folder: Carpeta raíz de wallpapers.
            recursive: Si escanea subcarpetas.
            image_extensions: Extensiones de imagen soportadas.
            video_extensions: Extensiones de vídeo soportadas.
        """
        self.folder: Path = expand(folder)
        self.recursive: bool = recursive
        self._image_exts = tuple(
            e.lower() for e in (image_extensions or (".png", ".jpg", ".jpeg", ".webp", ".bmp"))
        )
        self._video_exts = tuple(
            e.lower() for e in (video_extensions or (".mp4", ".webm", ".gif"))
        )
        self._items: list[WallpaperItem] = []
        self._lock = threading.RLock()
        self._observer = None  # watchdog observer, instanciado en watch()

    # ------------------------------------------------------------------ #
    # Escaneo
    # ------------------------------------------------------------------ #
    def scan(self) -> list[WallpaperItem]:
        """Escanea la carpeta y devuelve los wallpapers encontrados.

        Returns:
            Lista de :class:`WallpaperItem` ordenada por nombre.
        """
        with self._lock:
            items: list[WallpaperItem] = []
            if not self.folder.exists():
                logger.warning("Wallpaper folder does not exist: %s", self.folder)
                self._items = []
                return self._items

            try:
                iterator = (
                    self.folder.rglob("*") if self.recursive else self.folder.iterdir()
                )
            except (PermissionError, OSError) as exc:
                logger.warning("Could not scan %s: %s", self.folder, exc)
                self._items = []
                return self._items

            for entry in iterator:
                try:
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                        continue
                    items.append(WallpaperItem.from_path(entry))
                except (PermissionError, OSError, ValueError) as exc:
                    logger.debug("Ignoring %s: %s", entry, exc)

            items.sort(key=lambda i: i.name.lower())
            self._items = items
            logger.info("Library scanned: %d wallpapers in %s", len(items), self.folder)
            return list(self._items)

    @property
    def items(self) -> list[WallpaperItem]:
        """Lista actual de wallpapers (caché)."""
        with self._lock:
            return list(self._items)

    def __iter__(self) -> Iterator[WallpaperItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------ #
    # Filtrado y búsqueda
    # ------------------------------------------------------------------ #
    def filter(
        self,
        *,
        types: Iterable[WallpaperType] | None = None,
        search: str = "",
        favorites: set[Path] | None = None,
        only_favorites: bool = False,
    ) -> list[WallpaperItem]:
        """Filtra la biblioteca por tipo y búsqueda textual.

        Args:
            types: Tipos permitidos. ``None`` = todos.
            search: Texto a buscar en el nombre (case-insensitive).
            favorites: Conjunto de rutas favoritas.
            only_favorites: Si ``True``, devuelve sólo favoritos.

        Returns:
            Lista de items que cumplen los criterios.
        """
        with self._lock:
            items = list(self._items)

        if types is not None:
            type_set = set(types)
            items = [i for i in items if i.type in type_set]

        if search:
            needle = search.lower().strip()
            items = [i for i in items if needle in i.name.lower()]

        if only_favorites and favorites is not None:
            fav_set = {f.resolve() for f in favorites}
            items = [i for i in items if i.path.resolve() in fav_set]

        return items

    def find(self, path: Path | str) -> WallpaperItem | None:
        """Busca un item por ruta exacta."""
        target = expand(path).resolve()
        for item in self._items:
            if item.path.resolve() == target:
                return item
        return None

    # ------------------------------------------------------------------ #
    # Observación en vivo (watchdog)
    # ------------------------------------------------------------------ #
    def watch(self, on_change) -> None:
        """Comienza a observar la carpeta en busca de cambios.

        Usa :mod:`watchdog` para detectar archivos añadidos/eliminados.
        En cada cambio se ejecuta ``on_change`` (sin argumentos).

        Args:
            on_change: Callback invocado en cada cambio.
        """
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.warning("watchdog no instalado; observación deshabilitada")
            return

        class _Handler(FileSystemEventHandler):
            def __init__(self_inner) -> None:
                self_inner._debounce = 0.0

            def on_any_event(self_inner, event) -> None:  # noqa: D401
                if event.is_directory:
                    return
                if not event.src_path.lower().endswith(self.SUPPORTED_EXTENSIONS):
                    return
                now = datetime.now().timestamp()
                if now - self_inner._debounce < 0.5:
                    return
                self_inner._debounce = now
                logger.debug("Change detected: %s", event.src_path)
                try:
                    on_change()
                except Exception:  # noqa: BLE001
                    logger.exception("Error in watch callback")

        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:  # noqa: BLE001
                pass

        self._observer = Observer()
        self._observer.schedule(
            _Handler(),
            str(self.folder),
            recursive=self.recursive,
        )
        self._observer.daemon = True
        self._observer.start()
        logger.info("Watching for changes in %s", self.folder)

    def stop_watching(self) -> None:
        """Detiene la observación de la carpeta."""
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:  # noqa: BLE001
                pass
            self._observer = None

    # ------------------------------------------------------------------ #
    # Añadir archivos
    # ------------------------------------------------------------------ #
    def add_file(self, source: Path | str, *, copy: bool = True) -> WallpaperItem | None:
        """Añade un archivo a la biblioteca (copiándolo o moviéndolo).

        Args:
            source: Ruta del archivo origen.
            copy: Si ``True`` copia el archivo; si ``False`` lo mueve.

        Returns:
            :class:`WallpaperItem` creado o ``None`` si falló.
        """
        import shutil

        src = expand(source)
        if not src.exists():
            logger.error("File to add does not exist: %s", src)
            return None

        if src.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            logger.warning("Unsupported extension: %s", src.suffix)
            return None

        self.folder.mkdir(parents=True, exist_ok=True)
        dst = self.folder / src.name
        if dst.exists():
            stem, suffix = dst.stem, dst.suffix
            counter = 1
            while True:
                candidate = self.folder / f"{stem}_{counter}{suffix}"
                if not candidate.exists():
                    dst = candidate
                    break
                counter += 1

        try:
            if copy:
                shutil.copy2(src, dst)
            else:
                shutil.move(src, dst)
        except OSError as exc:
            logger.error("Could not add %s: %s", src, exc)
            return None

        item = WallpaperItem.from_path(dst)
        with self._lock:
            self._items.append(item)
            self._items.sort(key=lambda i: i.name.lower())
        logger.info("Wallpaper added: %s", dst)
        return item

    def remove_file(self, path: Path | str, *, delete: bool = False) -> bool:
        """Elimina un wallpaper de la biblioteca.

        Args:
            path: Ruta del archivo a eliminar.
            delete: Si ``True`` borra el archivo del disco.

        Returns:
            ``True`` si se eliminó de la biblioteca.
        """
        target = expand(path).resolve()
        with self._lock:
            before = len(self._items)
            self._items = [i for i in self._items if i.path.resolve() != target]
            removed = len(self._items) < before

        if removed and delete:
            try:
                target.unlink()
            except OSError as exc:
                logger.warning("Could not delete %s: %s", target, exc)
        return removed
