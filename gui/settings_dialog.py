from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from backend.wallpaper_manager import WallpaperManager
    from config.settings import Settings

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    def __init__(self, manager: "WallpaperManager", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._settings = manager.settings
        self.setWindowTitle("Settings — Frostwall")
        self.setMinimumSize(640, 480)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_appearance_tab(), "Appearance")
        self.tabs.addTab(self._build_integration_tab(), "Integration")
        self.tabs.addTab(self._build_rotation_tab(), "Rotation")
        self.tabs.addTab(self._build_notifications_tab(), "Notifications")
        self.tabs.addTab(self._build_io_tab(), "Import/Export")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setObjectName("PrimaryButton")
        save_btn.setText("Save")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setObjectName("DialogButton")
        cancel_btn.setText("Cancel")
        default_btn = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        default_btn.setObjectName("DialogButton")
        default_btn.setText("Defaults")

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        default_btn.clicked.connect(self._restore_defaults)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        self.wallpaper_folder_edit = QLineEdit()
        self.wallpaper_folder_edit.setPlaceholderText("~/Pictures/Wallpapers")
        browse_btn = self._browse_button(self.wallpaper_folder_edit, "Wallpaper folder")
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.wallpaper_folder_edit)
        folder_row.addWidget(browse_btn)
        form.addRow("Wallpaper folder:", self._wrap(folder_row))

        self.recursive_check = QCheckBox("Scan subfolders recursively")
        form.addRow("", self.recursive_check)

        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(96, 512)
        self.thumbnail_size_spin.setSingleStep(16)
        self.thumbnail_size_spin.setSuffix(" px")
        form.addRow("Thumbnail size:", self.thumbnail_size_spin)

        return tab

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(2, 10)
        form.addRow("Grid columns:", self.columns_spin)

        self.show_filenames_check = QCheckBox("Show file names")
        form.addRow("", self.show_filenames_check)

        self.animations_check = QCheckBox("Enable animations")
        form.addRow("", self.animations_check)

        return tab

    def _build_integration_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        self.hyprpaper_exec_edit = QLineEdit()
        form.addRow("Hyprpaper:", self.hyprpaper_exec_edit)

        self.hyprpaper_conf_edit = QLineEdit()
        browse = self._browse_button(self.hyprpaper_conf_edit, "Config file")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.hyprpaper_conf_edit)
        row.addWidget(browse)
        form.addRow("Config path:", self._wrap(row))

        self.mpvpaper_exec_edit = QLineEdit()
        form.addRow("Mpvpaper:", self.mpvpaper_exec_edit)

        self.mpv_options_edit = QLineEdit()
        self.mpv_options_edit.setPlaceholderText("--no-audio --loop-file --panscan=1.0")
        self.mpv_options_edit.setToolTip(
            "Flags passed to mpv for animated wallpapers. Add --hwdec=auto-safe\n"
            "to use GPU decoding (reduces CPU). Add --framedrop=decoder to\n"
            "drop frames when system is under load."
        )
        form.addRow("MPV options:", self.mpv_options_edit)

        self.default_monitor_edit = QLineEdit()
        self.default_monitor_edit.setPlaceholderText("(auto)")
        form.addRow("Default monitor:", self.default_monitor_edit)

        self.autostart_check = QCheckBox("Start automatically with Hyprland")
        form.addRow("", self.autostart_check)

        self.restore_check = QCheckBox("Restore last wallpaper on startup")
        form.addRow("", self.restore_check)

        return tab

    def _build_rotation_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        self.rotation_check = QCheckBox("Enable automatic rotation")
        form.addRow("", self.rotation_check)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(30, 86400)
        self.interval_spin.setSingleStep(60)
        self.interval_spin.setSuffix(" s")
        form.addRow("Rotation interval:", self.interval_spin)

        self.random_check = QCheckBox("Random order")
        form.addRow("", self.random_check)

        return tab

    def _build_notifications_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        self.notif_enabled = QCheckBox("Enable desktop notifications")
        form.addRow("", self.notif_enabled)

        self.notif_on_change = QCheckBox("Notify on wallpaper change")
        form.addRow("", self.notif_on_change)

        self.notif_on_errors = QCheckBox("Notify on errors")
        form.addRow("", self.notif_on_errors)

        return tab

    def _build_io_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        info = QLabel(
            "Export or import your full Frostwall configuration as a JSON file."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_export = QPushButton("Export…")
        btn_export.setObjectName("DialogButton")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.clicked.connect(self._export_config)
        layout.addWidget(btn_export)

        btn_import = QPushButton("Import…")
        btn_import.setObjectName("DialogButton")
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.clicked.connect(self._import_config)
        layout.addWidget(btn_import)

        layout.addStretch()
        return tab

    @staticmethod
    def _wrap(layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _browse_button(line_edit: QLineEdit, title: str) -> QPushButton:
        btn = QPushButton("Browse…")
        btn.setObjectName("DialogButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _open():
            path = QFileDialog.getExistingDirectory(None, title, line_edit.text() or "~")
            if path:
                line_edit.setText(path)

        btn.clicked.connect(_open)
        return btn

    def _load_values(self) -> None:
        s = self._settings
        self.wallpaper_folder_edit.setText(str(s.get("wallpapers.folder", "")))
        self.recursive_check.setChecked(bool(s.get("wallpapers.recursive_scan", True)))
        self.thumbnail_size_spin.setValue(int(s.get("wallpapers.thumbnail_size", 220)))

        self.columns_spin.setValue(int(s.get("ui.grid_columns", 4)))
        self.show_filenames_check.setChecked(bool(s.get("ui.show_filenames", True)))
        self.animations_check.setChecked(bool(s.get("ui.animations_enabled", True)))

        self.hyprpaper_exec_edit.setText(str(s.get("hyprpaper.executable", "hyprpaper")))
        self.hyprpaper_conf_edit.setText(str(s.get("hyprpaper.config_path", "")))
        self.mpvpaper_exec_edit.setText(str(s.get("mpvpaper.executable", "mpvpaper")))
        self.mpv_options_edit.setText(str(s.get("mpvpaper.mpv_options", "")))
        self.default_monitor_edit.setText(str(s.get("hyprland.default_monitor", "")))
        self.autostart_check.setChecked(bool(s.get("startup.auto_start", False)))
        self.restore_check.setChecked(bool(s.get("startup.restore_last", True)))

        self.rotation_check.setChecked(bool(s.get("rotation.enabled", False)))
        self.interval_spin.setValue(int(s.get("rotation.interval_seconds", 1800)))
        self.random_check.setChecked(bool(s.get("rotation.random_order", False)))

        self.notif_enabled.setChecked(bool(s.get("notifications.enabled", True)))
        self.notif_on_change.setChecked(bool(s.get("notifications.on_wallpaper_change", True)))
        self.notif_on_errors.setChecked(bool(s.get("notifications.on_errors", True)))

    def accept(self) -> None:
        s = self._settings
        s.set("wallpapers.folder", self.wallpaper_folder_edit.text() or "~/Pictures/Wallpapers")
        s.set("wallpapers.recursive_scan", self.recursive_check.isChecked())
        s.set("wallpapers.thumbnail_size", self.thumbnail_size_spin.value())

        s.set("ui.grid_columns", self.columns_spin.value())
        s.set("ui.show_filenames", self.show_filenames_check.isChecked())
        s.set("ui.animations_enabled", self.animations_check.isChecked())

        s.set("hyprpaper.executable", self.hyprpaper_exec_edit.text() or "hyprpaper")
        s.set("hyprpaper.config_path", self.hyprpaper_conf_edit.text())
        s.set("mpvpaper.executable", self.mpvpaper_exec_edit.text() or "mpvpaper")
        s.set("mpvpaper.mpv_options", self.mpv_options_edit.text())
        s.set("hyprland.default_monitor", self.default_monitor_edit.text())
        s.set("startup.auto_start", self.autostart_check.isChecked())
        s.set("startup.restore_last", self.restore_check.isChecked())

        s.set("rotation.enabled", self.rotation_check.isChecked())
        s.set("rotation.interval_seconds", self.interval_spin.value())
        s.set("rotation.random_order", self.random_check.isChecked())

        s.set("notifications.enabled", self.notif_enabled.isChecked())
        s.set("notifications.on_wallpaper_change", self.notif_on_change.isChecked())
        s.set("notifications.on_errors", self.notif_on_errors.isChecked())

        try:
            self._manager.library.folder = self._settings.expand_path(
                self._settings.get("wallpapers.folder", "")
            )
        except Exception:
            logger.debug("Could not update library folder")

        if self.autostart_check.isChecked():
            self._manager.enable_autostart()
        else:
            self._manager.disable_autostart()

        super().accept()

    def _restore_defaults(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Restore defaults",
            "Reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._settings.reset_to_defaults()
        self._load_values()
        QMessageBox.information(self, "Done", "Settings have been restored to defaults.")

    def _export_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export configuration",
            "frostwall-config.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            self._settings.export_to(path)
            QMessageBox.information(self, "Exported", f"Configuration saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not export:\n{exc}")

    def _import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import configuration",
            "~",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            self._settings.import_from(path)
            self._load_values()
            QMessageBox.information(self, "Imported", "Configuration imported successfully.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not import:\n{exc}")
