"""
File Utils
==========

Utilidades para identificar y manipular archivos de wallpaper.

Define extensiones soportadas, helpers de tipo de archivo y utilidades
comunes (hash, tamaño humano, etc.).
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensiones soportadas. En minúsculas, con punto inicial.
SUPPORTED_IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
SUPPORTED_VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".webm", ".gif")


def is_image(path: Path | str) -> bool:
    """Indica si ``path`` es una imagen soportada."""
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_video(path: Path | str) -> bool:
    """Indica si ``path`` es un vídeo soportado (incluye GIF)."""
    return Path(path).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def is_gif(path: Path | str) -> bool:
    """Indica si ``path`` es un GIF (estático o animado)."""
    return Path(path).suffix.lower() == ".gif"


def is_animated(path: Path | str) -> bool:
    """Indica si ``path`` corresponde a un fondo animado.

    Se consideran animados los MP4, WEBM y los GIF con múltiples frames.
    Para GIFs se realiza una inspección mínima de cabecera.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".mp4", ".webm"):
        return True
    if suffix == ".gif":
        return _gif_is_animated(p)
    return False


def _gif_is_animated(path: Path) -> bool:
    """Comprueba si un GIF tiene múltiples frames leyendo su cabecera.

    Usa :mod:`PIL` si está disponible; en caso contrario asume animado.
    """
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            # ``n_frames`` sólo existe en imágenes con múltiples frames.
            return getattr(img, "n_frames", 1) > 1
    except Exception:  # noqa: BLE001
        logger.debug("Could not inspect GIF %s, assuming animated", path)
        return True


def file_hash(path: Path | str, *, algorithm: str = "sha256",
              chunk_size: int = 1 << 16) -> str:
    """Calcula el hash criptográfico de un archivo.

    Args:
        path: Ruta del archivo.
        algorithm: Nombre del algoritmo de ``hashlib`` (por defecto sha256).
        chunk_size: Tamaño de bloque para lectura.

    Returns:
        Hexdigest del hash calculado.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path | str) -> Path:
    """Asegura que ``path`` existe, creándolo si hace falta."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def human_size(num_bytes: int) -> str:
    """Convierte bytes a una representación humana (KB, MB, ...).

    Args:
        num_bytes: Tamaño en bytes.

    Returns:
        Cadena como ``"1.4 MB"``.
    """
    if num_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def expand(path: Path | str) -> Path:
    """Expande ``~`` y variables de entorno en ``path``."""
    return Path(os.path.expandvars(os.path.expanduser(str(path))))


def safe_rename(src: Path | str, dst: Path | str) -> Path:
    """Renombra o mueve ``src`` a ``dst`` de forma segura.

    Si el destino existe se añade un sufijo numérico.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    if dst_path.exists():
        stem, suffix = dst_path.stem, dst_path.suffix
        counter = 1
        while True:
            candidate = dst_path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                dst_path = candidate
                break
            counter += 1
    src_path.rename(dst_path)
    return dst_path
