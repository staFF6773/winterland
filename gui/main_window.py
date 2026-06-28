from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QObject,
    QThread,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from backend.library import WallpaperItem, WallpaperType
from backend.wallpaper_manager import WallpaperManager, WallpaperManagerError
from utils.file_utils import is_image
from utils.logger import get_logger
from gui.components.search_bar import SearchBar
from gui.preview_panel import PreviewPanel
from gui.settings_dialog import SettingsDialog
from gui.sidebar import (
    SECTION_FAVORITES,
    SECTION_HISTORY,
    SECTION_LIBRARY,
    SECTION_PLAYLISTS,
    SECTION_SETTINGS,
    Sidebar,
)
from gui.wallpaper_grid import WallpaperGrid

if TYPE_CHECKING:
    from ..config.settings import Settings

logger = get_logger(__name__)


class ThumbnailLoader(QObject):
    thumbnail_ready = Signal(object, object)
    thumbnail_error = Signal(object)
    load_requested = Signal(str)

    def __init__(self, thumbnailer) -> None:
        super().__init__()
        self._thumbnailer = thumbnailer

    @Slot(str)
    def load(self, path_str: str) -> None:
        path = Path(path_str)
        try:
            thumb_path = self._thumbnailer.get_or_create(path)
            from PySide6.QtGui import QImage

            image = QImage(str(thumb_path))
            if image.isNull():
                logger.debug("Null thumbnail: %s", thumb_path)
                self.thumbnail_error.emit(path)
            else:
                self.thumbnail_ready.emit(path, image)
        except Exception as exc:
            logger.debug("Error generating thumbnail for %s: %s", path, exc)
            self.thumbnail_error.emit(path)


class MainWindow(QMainWindow):
    def __init__(self, manager: WallpaperManager, theme) -> None:
        super().__init__()
        self.manager: WallpaperManager = manager
        self.settings: "Settings" = manager.settings
        self._theme = theme
        self._preview_visible = True

        self.setWindowTitle("Frostwall")
        self.setObjectName("MainWindow")
        self.setMinimumSize(900, 600)
        self.resize(
            int(self.settings.get("ui.window_geometry.width", 1200)),
            int(self.settings.get("ui.window_geometry.height", 750)),
        )

        self._current_section: str = SECTION_LIBRARY
        self._current_filter: set[WallpaperType] | None = None
        self._current_search: str = ""
        self._selected_item: WallpaperItem | None = None
        self._active_paths: set[Path] = self._load_active_wallpapers()

        self._thumb_thread = QThread()
        self._thumb_loader = ThumbnailLoader(self.thumbnailer)
        self._thumb_loader.moveToThread(self._thumb_thread)
        self._thumb_loader.load_requested.connect(
            self._thumb_loader.load, Qt.ConnectionType.QueuedConnection
        )
        self._thumb_loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_loader.thumbnail_error.connect(self._on_thumbnail_error)
        self._thumb_thread.start()

        self._build_ui()
        self._build_shortcuts()
        self._connect_manager()
        self._reload_library()

        if self.settings.get("startup.restore_last", True):
            try:
                self.manager.restore_last()
            except Exception:
                logger.debug("Could not restore last wallpaper")

    def _make_thumbnailer(self):
        from utils.thumbnailer import Thumbnailer

        cache = self.settings.get("wallpapers.thumbnail_cache", "")
        size = int(self.settings.get("wallpapers.thumbnail_size", 220))
        return Thumbnailer(cache_dir=cache, size=size)

    @property
    def thumbnailer(self):
        if not hasattr(self, "_thumbnailer_instance"):
            self._thumbnailer_instance = self._make_thumbnailer()
        return self._thumbnailer_instance

    def _load_active_wallpapers(self) -> set[Path]:
        last: dict[str, str] = self.settings.get("startup.last_wallpapers", {}) or {}
        paths: set[Path] = set()
        for p in last.values():
            try:
                paths.add(Path(p))
            except Exception:
                continue
        return paths

    def _track_active(self, item: WallpaperItem) -> None:
        self.grid.set_active(item.path, True)
        for path in list(self._active_paths):
            if path != item.path:
                self.grid.set_active(path, False)
        self._active_paths = {item.path}

    def _update_active_states(self) -> None:
        for path in self._active_paths:
            self.grid.set_active(path, True)

    def _run_wallust(self, path: Path) -> None:
        try:
            palette = self._theme.palette
            if palette.run(path):
                self._theme.apply_wallust_colors()
                logger.info("Wallust theme applied from %s", path.name)
        except Exception:
            logger.debug("Wallust integration failed", exc_info=True)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.section_changed.connect(self._on_section_changed)
        layout.addWidget(self.sidebar)

        center = QFrame()
        center.setObjectName("Center")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        center_layout.addLayout(self._build_topbar())
        self.grid = WallpaperGrid()
        self.grid.wallpaper_activated.connect(self._on_wallpaper_activated)
        self.grid.wallpaper_selected.connect(self._on_wallpaper_selected)
        self.grid.favorites_toggled.connect(self._on_favorite_toggled)
        self.grid.remove_requested.connect(self._on_remove_requested)
        self.grid.add_to_playlist.connect(self._on_add_to_playlist)
        self.grid.files_dropped.connect(self._on_files_dropped)
        self.grid.set_columns(int(self.settings.get("ui.grid_columns", 5)))
        center_layout.addWidget(self.grid, 1)

        layout.addWidget(center, 1)

        self.preview = PreviewPanel(self.manager)
        self.preview.apply_requested.connect(self._on_apply_requested)
        self.preview.play_requested.connect(
            lambda: self.manager.mpvpaper.play_pause()
        )
        self.preview.pause_requested.connect(
            lambda: self.manager.mpvpaper.play_pause()
        )
        self.preview.stop_requested.connect(self.manager.mpvpaper.stop)
        self.preview.restart_requested.connect(self.manager.mpvpaper.restart)
        layout.addWidget(self.preview)

    def _build_topbar(self) -> QHBoxLayout:
        topbar = QHBoxLayout()
        topbar.setContentsMargins(24, 12, 24, 8)
        topbar.setSpacing(8)

        self.search_bar = SearchBar(placeholder="Search wallpapers...")
        self.search_bar.setFixedWidth(240)
        self.search_bar.text_changed.connect(self._on_search_changed)
        topbar.addWidget(self.search_bar)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All", None)
        self.filter_combo.addItem("Images", {WallpaperType.IMAGE, WallpaperType.GIF})
        self.filter_combo.addItem("Videos", {WallpaperType.VIDEO, WallpaperType.ANIMATED_GIF})
        self.filter_combo.addItem("GIF", {WallpaperType.GIF, WallpaperType.ANIMATED_GIF})
        self.filter_combo.setFixedWidth(120)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        topbar.addWidget(self.filter_combo)

        topbar.addStretch()

        self.status_label = QLabel()
        self.status_label.setObjectName("StatusLabel")
        topbar.addWidget(self.status_label)

        return topbar

    def _build_shortcuts(self) -> None:
        shortcuts = self.settings.get("shortcuts", {}) or {}

        mapping: dict[str, callable] = {
            "add_wallpaper": self._on_add_wallpaper,
            "search": self.search_bar.setFocus,
            "save_settings": self.settings.save,
            "open_settings": self._open_settings,
            "play_pause": lambda: self.manager.mpvpaper.play_pause(),
            "next_wallpaper": self._apply_next_wallpaper,
            "toggle_favorite": self._toggle_selected_favorite,
            "delete": self._delete_selected,
            "fullscreen": lambda: (
                self.showFullScreen()
                if not self.isFullScreen()
                else self.showNormal()
            ),
        }

        for key, callback in mapping.items():
            seq = shortcuts.get(key)
            if not seq:
                continue
            try:
                qt_seq = seq.replace("Comma", ",").replace("Ctrl", "Ctrl")
                shortcut = QShortcut(QKeySequence(qt_seq), self)
                shortcut.activated.connect(callback)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            except Exception:
                logger.warning("Invalid shortcut for %s: %s", key, seq)

        toggle_preview = QShortcut(QKeySequence("Ctrl+P"), self)
        toggle_preview.activated.connect(self._toggle_preview)
        toggle_preview.setContext(Qt.ShortcutContext.ApplicationShortcut)

    def _toggle_preview(self) -> None:
        self._preview_visible = not self._preview_visible
        self.preview.setVisible(self._preview_visible)

    def _connect_manager(self) -> None:
        self.manager.add_listener(self._on_manager_event)

    def _on_manager_event(self, event: str, payload: dict) -> None:
        if event == "wallpaper_applied":
            path_str = payload.get("path", "")
            if path_str:
                applied_path = Path(path_str)
                self.grid.set_active(applied_path, True)
                for p in list(self._active_paths):
                    if p != applied_path:
                        self.grid.set_active(p, False)
                self._active_paths = {applied_path}

                if self._theme.palette.available or self.settings.get("wallust.enabled", True):
                    self._run_wallust(applied_path)

            name = Path(payload.get("path", "")).name
            mon = payload.get("monitor", "all")
            self.status_label.setText(f"Applied: {name} on {mon}")
            self.sidebar.set_status("Applied", color="#9ece6a")
        elif event == "rotation_started":
            self.status_label.setText("Rotation started")
        elif event == "rotation_stopped":
            self.status_label.setText("Rotation stopped")

    @Slot(str)
    def _on_section_changed(self, section: str) -> None:
        self._current_section = section

        if section == SECTION_SETTINGS:
            self._open_settings()
            self.sidebar.set_active(self._current_section)
            return

        self._reload_library()

    def _reload_library(self) -> None:
        self.manager.library.scan()
        self._apply_filters()

    def _apply_filters(self) -> None:
        only_favorites = self._current_section == SECTION_FAVORITES
        history_mode = self._current_section == SECTION_HISTORY

        if history_mode:
            items = []
            for entry in self.manager.history.recent(limit=50):
                path = Path(entry.path)
                if path.exists():
                    try:
                        items.append(WallpaperItem.from_path(path))
                    except Exception:
                        continue
        else:
            items = self.manager.library.filter(
                types=self._current_filter,
                search=self._current_search,
                favorites={p for p in self.manager.favorites.list()},
                only_favorites=only_favorites,
            )

        self.grid.set_items(items)

        fav_set = {Path(p) for p in self.manager.favorites.list()}
        for item in items:
            self.grid.set_favorite(item.path, item.path in fav_set)

        self._update_active_states()

        for item in items:
            self._load_thumbnail(item.path)

    def _load_thumbnail(self, path: Path) -> None:
        if is_image(path):
            self._load_thumbnail_sync(path)
        else:
            self._thumb_loader.load_requested.emit(str(path))

    def _load_thumbnail_sync(self, path: Path) -> None:
        try:
            thumb_path = self.thumbnailer.get_or_create(path)
            from PySide6.QtGui import QImage, QPixmap

            image = QImage(str(thumb_path))
            if not image.isNull():
                self.grid.update_thumbnail(path, QPixmap.fromImage(image))
            else:
                self.grid.set_thumbnail_error(path)
        except Exception as exc:
            logger.debug("Error loading thumbnail (sync): %s: %s", path, exc)
            self.grid.set_thumbnail_error(path)

    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        self._current_search = text
        self._apply_filters()

    @Slot(int)
    def _on_filter_changed(self, _index: int) -> None:
        self._current_filter = self.filter_combo.currentData()
        self._apply_filters()

    @Slot(object)
    def _on_wallpaper_selected(self, item: WallpaperItem) -> None:
        self._selected_item = item
        self.preview.set_item(item)
        from PySide6.QtGui import QPixmap

        try:
            if item.type == WallpaperType.IMAGE or not item.is_animated:
                pixmap = QPixmap(str(item.path))
                if not pixmap.isNull():
                    self.preview.set_preview_pixmap(pixmap)
                    return
            else:
                try:
                    thumb_path = self.thumbnailer.get_or_create(item.path)
                    pixmap = QPixmap(str(thumb_path))
                    if not pixmap.isNull():
                        self.preview.set_preview_pixmap(pixmap)
                        return
                except Exception as exc:
                    logger.debug("No thumbnail for preview: %s", exc)
        except Exception as exc:
            logger.debug("Could not load preview: %s", exc)

        self.preview.preview_label.setText(
            "Preview not available" if item.is_animated else "Error loading"
        )
        self.preview.preview_label.setPixmap(QPixmap())

    @Slot(object)
    def _on_wallpaper_activated(self, item: WallpaperItem) -> None:
        monitor = self.preview.monitor_combo.currentData() or ""
        try:
            self.manager.apply(item.path, monitor=monitor)
            self._track_active(item)
        except WallpaperManagerError as exc:
            QMessageBox.critical(self, "Error", str(exc))

    @Slot(object, str)
    def _on_apply_requested(self, item: WallpaperItem, monitor: str) -> None:
        try:
            if monitor == "":
                self.manager.apply_to_all_monitors(item.path)
            else:
                self.manager.apply(item.path, monitor=monitor)
            self._track_active(item)
        except WallpaperManagerError as exc:
            QMessageBox.critical(self, "Error", str(exc))

    @Slot(object)
    def _on_favorite_toggled(self, item: WallpaperItem) -> None:
        is_fav = self.manager.favorites.toggle(item.path)
        self.grid.set_favorite(item.path, is_fav)
        name = item.name
        self.status_label.setText(
            f"{'★ Added to' if is_fav else '☆ Removed from'} favorites: {name}"
        )

    @Slot(object)
    def _on_remove_requested(self, item: WallpaperItem) -> None:
        confirm = QMessageBox.question(
            self,
            "Remove wallpaper",
            f"Remove '{item.path.name}' from library?\n"
            "(File on disk will not be deleted)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.manager.library.remove_file(item.path, delete=False):
            self.status_label.setText(f"Removed: {item.name}")
            self._apply_filters()

    @Slot(object)
    def _on_add_to_playlist(self, item: WallpaperItem) -> None:
        playlists = self.manager.playlists.all()
        if not playlists:
            playlist = self.manager.playlists.create("Default")
        else:
            playlist = playlists[0]
        self.manager.playlists.add_to(playlist.id, item.path)
        self.status_label.setText(
            f"Added to playlist '{playlist.name}': {item.name}"
        )

    @Slot(list)
    def _on_files_dropped(self, paths: list[str]) -> None:
        added = 0
        for raw in paths:
            item = self.manager.library.add_file(raw, copy=True)
            if item is not None:
                added += 1
        if added:
            self.status_label.setText(f"{added} wallpaper(s) added")
            self._apply_filters()

    def _on_add_wallpaper(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select wallpapers",
            os.path.expanduser("~"),
            "Images & Videos (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.webm *.gif)",
        )
        if not files:
            return
        added = 0
        for path in files:
            if self.manager.library.add_file(path, copy=True):
                added += 1
        if added:
            self.status_label.setText(f"{added} wallpaper(s) added")
            self._apply_filters()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.manager, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.grid.set_columns(int(self.settings.get("ui.grid_columns", 5)))
            self.status_label.setText("Settings saved")

    def _apply_next_wallpaper(self) -> None:
        items = self.manager.library.items
        if not items:
            return
        last = self.manager.history.last()
        next_item = items[0]
        if last:
            for i, item in enumerate(items):
                if str(item.path) == last.path:
                    next_item = items[(i + 1) % len(items)]
                    break
        try:
            self.manager.apply(next_item.path)
        except WallpaperManagerError as exc:
            self.status_label.setText(f"Error: {exc}")

    def _toggle_selected_favorite(self) -> None:
        if self._selected_item is not None:
            self._on_favorite_toggled(self._selected_item)

    def _delete_selected(self) -> None:
        if self._selected_item is not None:
            self._on_remove_requested(self._selected_item)

    @Slot(object, object)
    def _on_thumbnail_ready(self, path: object, image: object) -> None:
        if isinstance(path, Path):
            from PySide6.QtGui import QImage, QPixmap

            if isinstance(image, QImage):
                self.grid.update_thumbnail(path, QPixmap.fromImage(image))

    @Slot(object)
    def _on_thumbnail_error(self, path: object) -> None:
        if isinstance(path, Path):
            self.grid.set_thumbnail_error(path)

    def closeEvent(self, event) -> None:
        geo = self.geometry()
        self.settings.set("ui.window_geometry", {
            "width": geo.width(),
            "height": geo.height(),
            "x": geo.x(),
            "y": geo.y(),
        })
        self.settings.save()
        self.manager.cleanup()

        self._thumb_thread.quit()
        if not self._thumb_thread.wait(3000):
            logger.warning("Thumbnail thread did not finish in time")
            self._thumb_thread.terminate()

        super().closeEvent(event)
