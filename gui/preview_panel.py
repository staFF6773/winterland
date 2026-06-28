from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.library import WallpaperItem
from gui.theme import load_svg_icon

if TYPE_CHECKING:
    from backend.wallpaper_manager import WallpaperManager

logger = logging.getLogger(__name__)


class PreviewPanel(QFrame):
    apply_requested = Signal(object, str)
    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    restart_requested = Signal()

    def __init__(self, manager: "WallpaperManager", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._current_item: WallpaperItem | None = None
        self.setObjectName("PreviewPanel")
        self.setFixedWidth(280)
        self._build_ui()
        self._refresh_monitors()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Preview")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.preview_label = QLabel()
        self.preview_label.setObjectName("PreviewLabel")
        self.preview_label.setFixedSize(248, 140)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("Select a wallpaper")
        layout.addWidget(self.preview_label)

        self.name_label = QLabel("—")
        self.name_label.setObjectName("CardTitle")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("CardMeta")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        layout.addSpacing(4)

        self.monitor_combo = QComboBox()
        self.monitor_combo.setToolTip("Target monitor")
        layout.addWidget(self.monitor_combo)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_apply.setEnabled(False)
        layout.addWidget(self.btn_apply)

        controls_label = QLabel("Animation")
        controls_label.setObjectName("CardMeta")
        layout.addWidget(controls_label)

        controls = QHBoxLayout()
        controls.setSpacing(4)

        self.btn_play = self._icon_button("play", "Play", self.play_requested.emit)
        self.btn_pause = self._icon_button("pause", "Pause", self.pause_requested.emit)
        self.btn_stop = self._icon_button("stop", "Stop", self.stop_requested.emit)
        self.btn_restart = self._icon_button("restart", "Restart", self.restart_requested.emit)

        for btn in (self.btn_play, self.btn_pause, self.btn_stop, self.btn_restart):
            controls.addWidget(btn)
        layout.addLayout(controls)

        self.btn_apply_all = QPushButton("Apply to all monitors")
        self.btn_apply_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_all.clicked.connect(self._on_apply_all)
        self.btn_apply_all.setEnabled(False)
        layout.addWidget(self.btn_apply_all)

        layout.addStretch()

        self.state_label = QLabel("● Ready")
        self.state_label.setObjectName("CardMeta")
        layout.addWidget(self.state_label)

        self._set_animated_controls_enabled(False)

    def _icon_button(self, icon_name: str, tooltip: str, callback) -> QPushButton:
        from PySide6.QtCore import QSize

        btn = QPushButton()
        btn.setObjectName("IconButton")
        btn.setIcon(load_svg_icon(icon_name, color="#c0caf5", size=18))
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(32, 32)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    def set_item(self, item: WallpaperItem | None) -> None:
        self._current_item = item
        if item is None:
            self.preview_label.clear()
            self.preview_label.setText("Select a wallpaper")
            self.name_label.setText("—")
            self.meta_label.setText("")
            self.btn_apply.setEnabled(False)
            self.btn_apply_all.setEnabled(False)
            self._set_animated_controls_enabled(False)
            return

        self.name_label.setText(item.path.name)
        self.meta_label.setText(
            f"{item.type.value.upper()} · {item.human_size}"
        )
        self.btn_apply.setEnabled(True)
        self.btn_apply_all.setEnabled(True)
        self._set_animated_controls_enabled(item.is_animated)

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            248,
            140,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def _refresh_monitors(self) -> None:
        self.monitor_combo.clear()
        self.monitor_combo.addItem("All (primary)", "")
        try:
            for monitor in self._manager.monitors.monitors:
                self.monitor_combo.addItem(
                    f"{monitor.name} ({monitor.resolution})",
                    monitor.name,
                )
        except Exception:
            logger.debug("Could not list monitors")

    def set_state(self, text: str, *, color: str = "#9ece6a") -> None:
        self.state_label.setText(f"● {text}")

    def _set_animated_controls_enabled(self, enabled: bool) -> None:
        for btn in (self.btn_play, self.btn_pause, self.btn_stop, self.btn_restart):
            btn.setEnabled(enabled)

    def _on_apply(self) -> None:
        if self._current_item is None:
            return
        monitor = self.monitor_combo.currentData() or ""
        self.apply_requested.emit(self._current_item, monitor)

    def _on_apply_all(self) -> None:
        if self._current_item is None:
            return
        self.apply_requested.emit(self._current_item, "")

    def refresh_monitors(self) -> None:
        self._manager.refresh_monitors()
        self._refresh_monitors()
