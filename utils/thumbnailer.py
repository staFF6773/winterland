"""
Thumbnailer
===========

Generación y caché de miniaturas para imágenes y vídeos.

Las miniaturas se almacenan en ``~/.cache/wallpaper-manager/thumbnails``
con un nombre derivado del hash del archivo original, lo que permite
reutilizarlas sin regenerar.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Final

from utils.file_utils import ensure_dir, expand, is_image, is_video

logger = logging.getLogger(__name__)

# Tamaño por defecto de las miniaturas.
DEFAULT_SIZE: Final[int] = 220

# Tamaño máximo en bytes para procesar en memoria sin streaming.
_MAX_INMEMORY_BYTES = 50 * 1024 * 1024  # 50 MB


class ThumbnailError(RuntimeError):
    """Error al generar una miniatura."""


class Thumbnailer:
    """Genera miniaturas para imágenes y vídeos, con caché en disco.

    Attributes:
        cache_dir: Carpeta donde se guardan las miniaturas.
        size: Tamaño objetivo en píxeles (lado mayor).
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        *,
        size: int = DEFAULT_SIZE,
    ) -> None:
        """Inicializa el generador de miniaturas.

        Args:
            cache_dir: Carpeta destino. Si se omite se usa
                ``~/.cache/wallpaper-manager/thumbnails``.
            size: Tamaño de miniatura en píxeles.
        """
        self.cache_dir: Path = (
            expand(cache_dir)
            if cache_dir
            else Path(os.path.expanduser("~/.cache/frostwall/thumbnails"))
        )
        self.size: int = max(64, size)
        ensure_dir(self.cache_dir)

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def thumbnail_path(self, source: Path | str) -> Path:
        """Devuelve la ruta de la miniatura para ``source``.

        No garantiza que la miniatura exista todavía.
        """
        src = expand(source)
        try:
            digest = hashlib.sha256(
                str(src.resolve()).encode("utf-8")
            ).hexdigest()[:24]
        except OSError:
            digest = hashlib.sha256(str(src).encode("utf-8")).hexdigest()[:24]
        ext = ".png" if src.suffix.lower() == ".png" else ".jpg"
        return self.cache_dir / f"{digest}{ext}"

    def get_or_create(self, source: Path | str) -> Path:
        """Devuelve la miniatura existente o la genera.

        Args:
            source: Ruta del archivo original.

        Returns:
            Ruta a la miniatura.

        Raises:
            ThumbnailError: Si no se pudo generar la miniatura.
        """
        src = expand(source)
        if not src.exists():
            raise ThumbnailError(f"El archivo no existe: {src}")

        cached = self.thumbnail_path(src)
        if cached.exists() and cached.stat().st_mtime >= src.stat().st_mtime:
            return cached

        try:
            if is_image(src):
                self._generate_image_thumbnail(src, cached)
            elif is_video(src):
                self._generate_video_thumbnail(src, cached)
            else:
                raise ThumbnailError(f"Formato no soportado: {src.suffix}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error generating thumbnail for %s", src)
            raise ThumbnailError(str(exc)) from exc

        return cached

    def clear_cache(self) -> None:
        """Borra todas las miniaturas en caché."""
        for item in self.cache_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
            except OSError:
                logger.warning("Could not remove %s", item)

    # ------------------------------------------------------------------ #
    # Generación
    # ------------------------------------------------------------------ #
    def _generate_image_thumbnail(self, src: Path, dst: Path) -> None:
        """Genera miniatura de una imagen usando Pillow."""
        from PIL import Image  # type: ignore

        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((self.size, self.size))
            img.save(dst, format="JPEG", quality=85, optimize=True)

    def _generate_video_thumbnail(self, src: Path, dst: Path) -> None:
        """Genera miniatura de un vídeo o GIF animado con ffmpeg."""
        if not _has_ffmpeg():
            raise ThumbnailError(
                "ffmpeg no está disponible; instálalo para miniaturas de vídeo"
            )
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", str(src),
            "-ss", "00:00:01.000",
            "-frames:v", "1",
            "-vf", f"scale={self.size}:{self.size}:force_original_aspect_ratio=decrease",
            "-q:v", "3",
            str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise ThumbnailError(
                f"ffmpeg falló: {exc.stderr.decode('utf-8', 'ignore')[:200]}"
            ) from exc
        except FileNotFoundError as exc:
            raise ThumbnailError("ffmpeg no encontrado") from exc


def _has_ffmpeg() -> bool:
    """Comprueba si ``ffmpeg`` está disponible en el ``PATH``."""
    from shutil import which

    return which("ffmpeg") is not None
