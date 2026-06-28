from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QEnterEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.library import WallpaperItem

logger = logging.getLogger(__name__)


class ThumbnailCard(QFrame):
    clicked = Signal(object)
    double_clicked = Signal(object)
    favorite_toggled = Signal(object, bool)
    context_menu_requested = Signal(object, object)

    def __init__(self, item: WallpaperItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item: WallpaperItem = item
        self._is_favorite: bool = False
        self._selected: bool = False
        self._is_active: bool = False

        self.setObjectName("ThumbnailCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedSize(200, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self._build_ui()
        self._update_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.image_label = QLabel(self)
        self.image_label.setObjectName("ThumbnailImage")
        self.image_label.setFixedSize(200, 160)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("")
        self.image_label.setToolTip(self.item.path.name)

        self.corner_badge = QLabel(self.image_label)
        self.corner_badge.setObjectName("FavoriteBadge")
        self.corner_badge.setText("★")
        self.corner_badge.move(176, 6)
        self.corner_badge.setVisible(False)

        self.active_dot = QLabel(self.image_label)
        self.active_dot.setObjectName("ActiveDot")
        self.active_dot.setFixedSize(8, 8)
        self.active_dot.move(8, 8)
        self.active_dot.setVisible(False)

        layout.addWidget(self.image_label)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            200,
            160,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        from PySide6.QtCore import QRect

        x = max(0, (scaled.width() - 200) // 2)
        y = max(0, (scaled.height() - 160) // 2)
        cropped = scaled.copy(QRect(x, y, 200, 160))
        self.image_label.setPixmap(cropped)
        self.image_label.setText("")

    def set_loading(self) -> None:
        self.image_label.setText("")
        self.image_label.setPixmap(QPixmap())

    def set_error(self) -> None:
        self.image_label.setText("")
        self.image_label.setProperty("error", "true")
        self.image_label.style().unpolish(self.image_label)
        self.image_label.style().polish(self.image_label)
        self.image_label.setPixmap(QPixmap())

    def set_favorite(self, favorite: bool) -> None:
        self._is_favorite = favorite
        self.corner_badge.setVisible(favorite)

    @property
    def is_favorite(self) -> bool:
        return self._is_favorite

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.active_dot.setVisible(active)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_state()

    @property
    def is_selected(self) -> bool:
        return self._selected

    def _update_state(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_selected(True)
            self.clicked.emit(self.item)
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.item, event.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.item)

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
