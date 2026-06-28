from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from backend.library import WallpaperItem
from gui.theme import load_svg_icon

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class WallpaperContextMenu(QMenu):
    apply_requested = Signal(object)
    apply_all_requested = Signal(object)
    favorite_toggled = Signal(object)
    add_to_playlist = Signal(object)
    copy_path = Signal(object)
    remove_requested = Signal(object)
    open_folder = Signal(object)

    def __init__(self, item: WallpaperItem, is_favorite: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item: WallpaperItem = item
        self._is_favorite = is_favorite
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._build_actions()

    def _build_actions(self) -> None:
        act_apply = QAction(load_svg_icon("check", size=18), "Apply wallpaper", self)
        act_apply.triggered.connect(lambda: self.apply_requested.emit(self.item))
        self.addAction(act_apply)

        act_apply_all = QAction(
            load_svg_icon("monitor", size=18),
            "Apply to all monitors",
            self,
        )
        act_apply_all.triggered.connect(lambda: self.apply_all_requested.emit(self.item))
        self.addAction(act_apply_all)

        self.addSeparator()

        favorite_text = "Unfavorite" if self._is_favorite else "Favorite"
        act_fav = QAction(load_svg_icon("favorites", size=18), favorite_text, self)
        act_fav.triggered.connect(lambda: self.favorite_toggled.emit(self.item))
        self.addAction(act_fav)

        act_playlist = QAction(
            load_svg_icon("playlists", size=18),
            "Add to playlist…",
            self,
        )
        act_playlist.triggered.connect(lambda: self.add_to_playlist.emit(self.item))
        self.addAction(act_playlist)

        self.addSeparator()

        act_copy = QAction(load_svg_icon("download", size=18), "Copy path", self)
        act_copy.triggered.connect(lambda: self.copy_path.emit(self.item))
        self.addAction(act_copy)

        act_open = QAction(load_svg_icon("folder", size=18), "Open folder", self)
        act_open.triggered.connect(lambda: self.open_folder.emit(self.item))
        self.addAction(act_open)

        self.addSeparator()

        act_remove = QAction(load_svg_icon("delete", size=18), "Remove", self)
        act_remove.triggered.connect(lambda: self.remove_requested.emit(self.item))
        self.addAction(act_remove)

    def update_favorite_action(self, is_favorite: bool) -> None:
        for action in self.actions():
            if "favorite" in action.text().lower():
                action.setText("Unfavorite" if is_favorite else "Favorite")
                break

    def popup(self, pos: QPoint) -> None:
        super().popup(pos)
