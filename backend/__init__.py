"""
Backend
=======

Lógica de negocio de Wallpaper Manager.

Incluye integración con Hyprland (:mod:`hyprland`, :mod:`hyprpaper`,
:mod:`mpvpaper`), detección de monitores, biblioteca de wallpapers,
favoritos, historial, listas de reproducción y el gestor central.
"""

from backend.hyprland import Hyprland
from backend.monitor import Monitor, MonitorManager
from backend.hyprpaper import Hyprpaper, HyprpaperError
from backend.mpvpaper import Mpvpaper, MpvpaperError
from backend.library import Library, WallpaperItem, WallpaperType
from backend.favorites import Favorites
from backend.history import History, HistoryEntry
from backend.playlist import Playlist, PlaylistManager
from backend.wallpaper_manager import WallpaperManager, WallpaperManagerError

__all__ = [
    "Hyprland",
    "Monitor",
    "MonitorManager",
    "Hyprpaper",
    "HyprpaperError",
    "Mpvpaper",
    "MpvpaperError",
    "Library",
    "WallpaperItem",
    "WallpaperType",
    "Favorites",
    "History",
    "HistoryEntry",
    "Playlist",
    "PlaylistManager",
    "WallpaperManager",
    "WallpaperManagerError",
]
