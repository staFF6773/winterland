from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

WALLUST_CACHE: Final[Path] = Path.home() / ".cache" / "wallust" / "colors.json"

WALLUST_DEFAULTS: Final[dict[str, str]] = {
    "__BG__": "#1a1b26",
    "__SURFACE__": "#16161e",
    "__SURFACE_ALT__": "#24283b",
    "__FG__": "#c0caf5",
    "__FG_DIM__": "#565f89",
    "__ACCENT__": "#7aa2f7",
    "__ACCENT_HOVER__": "#89b0ff",
    "__BORDER__": "#2a2e42",
    "__ERROR__": "#f7768e",
    "__SUCCESS__": "#9ece6a",
    "__WARNING__": "#e0af68",
}


class WallustPalette:
    def __init__(self) -> None:
        self._colors: dict[str, str] = dict(WALLUST_DEFAULTS)
        self._available: bool = False

    @property
    def available(self) -> bool:
        return self._available

    def load_from_cache(self) -> bool:
        if not WALLUST_CACHE.exists():
            self._available = False
            return False
        try:
            data = json.loads(WALLUST_CACHE.read_text(encoding="utf-8"))
            colors = data.get("colors", {})
            special = data.get("special", {})

            self._colors["__BG__"] = special.get("background", WALLUST_DEFAULTS["__BG__"])
            self._colors["__FG__"] = special.get("foreground", WALLUST_DEFAULTS["__FG__"])
            self._colors["__SURFACE__"] = colors.get("color0", WALLUST_DEFAULTS["__SURFACE__"])
            self._colors["__SURFACE_ALT__"] = colors.get("color8", WALLUST_DEFAULTS["__SURFACE_ALT__"])
            self._colors["__ACCENT__"] = colors.get("color4", WALLUST_DEFAULTS["__ACCENT__"])
            self._colors["__ACCENT_HOVER__"] = colors.get("color12", WALLUST_DEFAULTS["__ACCENT_HOVER__"])
            self._colors["__BORDER__"] = colors.get("color8", WALLUST_DEFAULTS["__BORDER__"])
            self._colors["__ERROR__"] = colors.get("color1", WALLUST_DEFAULTS["__ERROR__"])
            self._colors["__SUCCESS__"] = colors.get("color2", WALLUST_DEFAULTS["__SUCCESS__"])
            self._colors["__WARNING__"] = colors.get("color3", WALLUST_DEFAULTS["__WARNING__"])
            self._colors["__FG_DIM__"] = colors.get("color8", WALLUST_DEFAULTS["__FG_DIM__"])

            self._available = True
            logger.info("Wallust palette loaded from cache")
            return True
        except Exception as exc:
            logger.debug("Failed to load Wallust palette: %s", exc)
            self._available = False
            return False

    def run(self, wallpaper_path: Path) -> bool:
        try:
            result = subprocess.run(
                ["wallust", "run", str(wallpaper_path)],
                capture_output=True,
                timeout=15,
            )
            if result.returncode != 0:
                logger.debug("wallust run failed: %s", result.stderr.decode())
                return False
            return self.load_from_cache()
        except FileNotFoundError:
            logger.debug("wallust not installed")
            return False
        except Exception as exc:
            logger.debug("wallust run error: %s", exc)
            return False

    def get(self, var: str) -> str:
        return self._colors.get(var, WALLUST_DEFAULTS.get(var, "#000000"))

    def apply_colors(self, stylesheet: str) -> str:
        result = stylesheet
        for var, color in self._colors.items():
            result = result.replace(var, color)
        return result

    def reset(self) -> None:
        self._colors = dict(WALLUST_DEFAULTS)
        self._available = False
