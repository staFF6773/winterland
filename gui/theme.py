from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from PySide6.QtCore import QObject, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from utils.wallust_integration import WallustPalette

logger = logging.getLogger(__name__)

_ASSETS_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "assets"
_ICONS_DIR: Final[Path] = _ASSETS_DIR / "icons"
_STYLES_DIR: Final[Path] = _ASSETS_DIR / "styles"


def load_stylesheet(name: str = "dark") -> str:
    path = _STYLES_DIR / f"{name}.qss"
    if not path.exists():
        logger.warning("Stylesheet not found: %s", path)
        return ""
    return path.read_text(encoding="utf-8")


def icon_path(name: str) -> Path:
    return _ICONS_DIR / f"{name}.svg"


def load_svg_icon(name: str, color: str = "#c0caf5", size: int = 24) -> QIcon:
    source = icon_path(name)
    if not source.exists():
        logger.warning("Icon not found: %s", source)
        return QIcon()

    try:
        svg_content = source.read_text(encoding="utf-8")
        svg_content = svg_content.replace("currentColor", color)
        renderer = QSvgRenderer(svg_content.encode("utf-8"))
        if not renderer.isValid():
            logger.warning("Invalid SVG: %s", source)
            return QIcon()
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception as exc:
        logger.exception("Error loading icon %s: %s", name, exc)
        return QIcon()


class ThemeManager(QObject):
    def __init__(self, app) -> None:
        super().__init__()
        self._app = app
        self._current: str = "dark"
        self._palette = WallustPalette()

    @property
    def palette(self) -> WallustPalette:
        return self._palette

    def apply(self, name: str = "dark") -> None:
        self._current = name
        raw = load_stylesheet(name)
        if not raw:
            return
        themed = self._palette.apply_colors(raw)
        self._app.setStyleSheet(themed)
        logger.info("Theme applied: %s (wallust=%s)", name, self._palette.available)

    def reload(self) -> None:
        self.apply(self._current)

    @property
    def current(self) -> str:
        return self._current

    def apply_wallust_colors(self) -> None:
        """Re-apply the current stylesheet with Wallust colors."""
        self.reload()
