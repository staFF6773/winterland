"""
Utils
=====

Utilidades transversales: logging, miniaturas, helpers de archivo y
notificaciones de escritorio.
"""

from utils.logger import get_logger, setup_logging
from utils.file_utils import (
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    is_image,
    is_video,
    is_gif,
    is_animated,
    file_hash,
    ensure_dir,
    human_size,
)
from utils.thumbnailer import Thumbnailer, ThumbnailError
from utils.notifications import Notifier, NotificationLevel

__all__ = [
    "get_logger",
    "setup_logging",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "SUPPORTED_VIDEO_EXTENSIONS",
    "is_image",
    "is_video",
    "is_gif",
    "is_animated",
    "file_hash",
    "ensure_dir",
    "human_size",
    "Thumbnailer",
    "ThumbnailError",
    "Notifier",
    "NotificationLevel",
]
