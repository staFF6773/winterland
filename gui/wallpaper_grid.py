from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QMimeData, Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.library import WallpaperItem
from gui.components.thumbnail_card import ThumbnailCard
from gui.components.context_menu import WallpaperContextMenu

logger = logging.getLogger(__name__)


CARD_WIDTH: int = 200
GRID_SPACING: int = 16


class WallpaperGrid(QFrame):
    wallpaper_activated = Signal(object)
    wallpaper_selected = Signal(object)
    context_menu = Signal(object, object)
    favorites_toggled = Signal(object)
    remove_requested = Signal(object)
    add_to_playlist = Signal(object)
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WallpaperGrid")
        self.setAcceptDrops(True)

        self._items: list[WallpaperItem] = []
        self._cards: dict[Path, ThumbnailCard] = {}
        self._columns: int = 4
        self._show_filenames: bool = True

        self._build_ui()
        self._adapt_columns()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._adapt_columns()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        self.empty_label = QLabel("No wallpapers here")
        self.empty_label.setObjectName("EmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(GRID_SPACING)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self._update_columns()

    def set_columns(self, columns: int) -> None:
        self._columns = max(1, columns)
        self._update_columns()
        self._rebuild_grid()

    def _adapt_columns(self) -> None:
        vw = self.scroll.viewport().width()
        if vw <= 0:
            return
        available = vw - self.grid_layout.contentsMargins().left() - self.grid_layout.contentsMargins().right()
        optimal = max(1, (available + GRID_SPACING) // (CARD_WIDTH + GRID_SPACING))
        if optimal != self._columns:
            self._columns = optimal
            self._update_columns()
            self._rebuild_grid()

    def set_show_filenames(self, show: bool) -> None:
        self._show_filenames = show

    def _update_columns(self) -> None:
        for i in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(i, 0)
        for i in range(self._columns):
            self.grid_layout.setColumnStretch(i, 1)

    def set_items(self, items: Iterable[WallpaperItem]) -> None:
        self._clear_cards()
        self._items = list(items)

        if not self._items:
            self.empty_label.setVisible(True)
            self.scroll.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.scroll.setVisible(True)

        for index, item in enumerate(self._items):
            card = ThumbnailCard(item)
            card.set_loading()
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_menu_requested.connect(self._on_context_menu)
            row, col = divmod(index, self._columns)
            self.grid_layout.addWidget(card, row, col)
            self._cards[item.path] = card

    def update_thumbnail(self, path: Path, pixmap) -> None:
        card = self._cards.get(path)
        if card is not None:
            card.set_thumbnail(pixmap)

    def set_thumbnail_error(self, path: Path) -> None:
        card = self._cards.get(path)
        if card is not None:
            card.set_error()

    def set_active(self, path: Path, active: bool) -> None:
        card = self._cards.get(path)
        if card is not None:
            card.set_active(active)

    def set_favorite(self, path: Path, favorite: bool) -> None:
        card = self._cards.get(path)
        if card is not None:
            card.set_favorite(favorite)

    def clear_selection(self) -> None:
        for card in self._cards.values():
            card.set_selected(False)

    def _clear_cards(self) -> None:
        for card in list(self._cards.values()):
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def _rebuild_grid(self) -> None:
        for index, (path, card) in enumerate(self._cards.items()):
            row, col = divmod(index, self._columns)
            self.grid_layout.removeWidget(card)
            self.grid_layout.addWidget(card, row, col)

    @Slot(object)
    def _on_card_clicked(self, item: WallpaperItem) -> None:
        self.clear_selection()
        card = self._cards.get(item.path)
        if card is not None:
            card.set_selected(True)
        self.wallpaper_selected.emit(item)

    @Slot(object)
    def _on_card_double_clicked(self, item: WallpaperItem) -> None:
        self.wallpaper_activated.emit(item)

    @Slot(object, object)
    def _on_context_menu(self, item: WallpaperItem, global_pos) -> None:
        path = item.path
        is_fav = path in self._cards and self._cards[path].is_favorite
        menu = WallpaperContextMenu(item, is_favorite=is_fav, parent=self)
        menu.apply_requested.connect(lambda i: self.wallpaper_activated.emit(i))
        menu.favorite_toggled.connect(lambda i: self.favorites_toggled.emit(i))
        menu.remove_requested.connect(lambda i: self.remove_requested.emit(i))
        menu.add_to_playlist.connect(lambda i: self.add_to_playlist.emit(i))
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.popup(global_pos)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths: list[str] = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                paths.append(local)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
