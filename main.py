#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path
from typing import Final

_PROJECT_DIR: Final[Path] = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from backend.wallpaper_manager import WallpaperManager, WallpaperManagerError
from config.settings import Settings, SettingsError
from gui.main_window import MainWindow
from gui.theme import ThemeManager
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def _check_environment() -> bool:
    if sys.version_info < (3, 12):
        print(
            f"Error: Python 3.12+ required (current: {sys.version.split()[0]})",
            file=sys.stderr,
        )
        return False

    if "WAYLAND_DISPLAY" not in os.environ and "DISPLAY" not in os.environ:
        logger.warning(
            "No graphical session detected (WAYLAND_DISPLAY/DISPLAY missing)."
        )

    if "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ:
        logger.warning(
            "Hyprland not running; some features will be unavailable."
        )
    return True


def _install_signal_handlers(app) -> None:
    def _handle_sigint(*_args) -> None:
        logger.info("Interrupt signal received; closing...")
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)


def main() -> int:
    setup_logging(level=logging.INFO)
    logger.info("Starting Frostwall...")

    if not _check_environment():
        return 1

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Frostwall")
    app.setApplicationDisplayName("Frostwall")
    app.setOrganizationName("Frostwall")
    app.setApplicationVersion("1.0.0")

    theme = ThemeManager(app)
    theme.palette.load_from_cache()
    theme.apply("dark")

    try:
        settings = Settings()
    except SettingsError as exc:
        logger.exception("Fatal configuration error: %s", exc)
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        manager = WallpaperManager(settings)
    except Exception as exc:
        logger.exception("Could not initialize WallpaperManager: %s", exc)
        print(f"Initialization error: {exc}", file=sys.stderr)
        return 3

    window = MainWindow(manager, theme)
    window.show()

    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    _install_signal_handlers(app)

    exit_code = app.exec()
    logger.info("Frostwall exited with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
