from __future__ import annotations

import logging
from typing import Final

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.theme import load_svg_icon

logger = logging.getLogger(__name__)

SECTION_LIBRARY: Final[str] = "library"
SECTION_FAVORITES: Final[str] = "favorites"
SECTION_HISTORY: Final[str] = "history"
SECTION_PLAYLISTS: Final[str] = "playlists"
SECTION_SETTINGS: Final[str] = "settings"

SECTIONS: Final[list[tuple[str, str, str]]] = [
    (SECTION_LIBRARY, "library", "Library"),
    (SECTION_FAVORITES, "favorites", "Favorites"),
    (SECTION_HISTORY, "history", "History"),
    (SECTION_PLAYLISTS, "playlists", "Playlists"),
    (SECTION_SETTINGS, "settings", "Settings"),
]


_ICON_DIM: str = "#565f89"
_ICON_HOVER: str = "#c0caf5"
_ICON_ACTIVE: str = "#7aa2f7"


class SidebarButton(QPushButton):
    def __init__(self, icon_name: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._hovered = False
        self.setObjectName("SidebarIconBtn")
        self.setIconSize(QSize(20, 20))
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(40, 40)
        self.setToolTip(text)
        self.setMouseTracking(True)
        self.toggled.connect(self._on_toggled)
        self._update_icon()

    def _icon_color(self) -> str:
        if self.isChecked():
            return _ICON_ACTIVE
        if self._hovered:
            return _ICON_HOVER
        return _ICON_DIM

    def _update_icon(self) -> None:
        self.setIcon(load_svg_icon(self._icon_name, color=self._icon_color(), size=20))

    def _on_toggled(self, _checked: bool) -> None:
        self._update_icon()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self._update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._update_icon()
        super().leaveEvent(event)


class Sidebar(QFrame):
    section_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(60)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._buttons: dict[str, SidebarButton] = {}

        for section_id, icon_name, label in SECTIONS:
            btn = SidebarButton(icon_name, label)
            self._group.addButton(btn)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
            self._buttons[section_id] = btn

        self.btn_library = self._buttons[SECTION_LIBRARY]
        self.btn_favorites = self._buttons[SECTION_FAVORITES]
        self.btn_history = self._buttons[SECTION_HISTORY]
        self.btn_playlists = self._buttons[SECTION_PLAYLISTS]
        self.btn_settings = self._buttons[SECTION_SETTINGS]

        self.btn_library.clicked.connect(lambda: self.section_changed.emit(SECTION_LIBRARY))
        self.btn_favorites.clicked.connect(lambda: self.section_changed.emit(SECTION_FAVORITES))
        self.btn_history.clicked.connect(lambda: self.section_changed.emit(SECTION_HISTORY))
        self.btn_playlists.clicked.connect(lambda: self.section_changed.emit(SECTION_PLAYLISTS))
        self.btn_settings.clicked.connect(lambda: self.section_changed.emit(SECTION_SETTINGS))

        self.btn_library.setChecked(True)

    def set_active(self, section: str) -> None:
        btn = self._buttons.get(section)
        if btn is not None:
            btn.setChecked(True)

    def set_status(self, text: str, *, color: str = "#9ece6a") -> None:
        self._dot.setStyleSheet(
            f"background-color: {color}; border-radius: 3px; min-width: 6px; max-width: 6px; min-height: 6px; max-height: 6px;"
        )
        self._dot.setToolTip(text)
