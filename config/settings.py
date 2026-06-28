"""
Settings
========

Gestión de configuración persistente de Wallpaper Manager.

La configuración se almacena en un archivo JSON en
``~/.config/wallpaper-manager/settings.json``. Si no existe, se crea a partir
de la plantilla por defecto ubicada en ``config/default_config.json``.

El acceso es tipo diccionario, con métodos de conveniencia para leer y
escribir secciones anidadas mediante rutas separadas por puntos, por ejemplo::

    settings.set("ui.grid_columns", 5)
    value = settings.get("ui.grid_columns", default=4)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Ruta base de configuración del usuario.
DEFAULT_CONFIG_PATH = Path(
    os.environ.get(
        "FROSTWALL_CONFIG_DIR",
        os.environ.get(
            "WALLPAPER_MANAGER_CONFIG_DIR",
            os.path.expanduser("~/.config/frostwall"),
        ),
    )
) / "settings.json"

# Ruta a la plantilla por defecto distribuida con el paquete.
_DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "default_config.json"


class SettingsError(RuntimeError):
    """Error lanzado cuando la configuración no puede ser cargada o guardada."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Mezcla ``override`` sobre ``base`` de forma recursiva.

    Args:
        base: Diccionario base (valores por defecto).
        override: Diccionario con valores que sobrescriben a ``base``.

    Returns:
        Nuevo diccionario con la mezcla profunda.
    """
    result: dict[str, Any] = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class Settings:
    """Gestor de configuración persistente basado en JSON.

    La clase es thread-safe gracias a un :class:`threading.RLock` interno.

    Attributes:
        path: Ruta absoluta al archivo de configuración del usuario.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        """Inicializa el gestor de configuración.

        Args:
            path: Ruta opcional al archivo de configuración. Si se omite se
                usa :data:`DEFAULT_CONFIG_PATH`.
        """
        self.path: Path = Path(path) if path else DEFAULT_CONFIG_PATH
        self._lock = RLock()
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Carga y guardado
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """Carga la configuración desde disco, fusionando con los valores
        por defecto. Si el archivo no existe lo crea.
        """
        with self._lock:
            try:
                defaults = self._load_defaults()
            except (OSError, json.JSONDecodeError) as exc:
                logger.exception("Could not load default configuration")
                raise SettingsError(str(exc)) from exc

            if not self.path.exists():
                logger.info("Creating initial config at %s", self.path)
                self._data = defaults
                self._write_to_disk()
                return

            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    user_data = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Configuración corrupta en %s, usando valores por defecto: %s",
                    self.path,
                    exc,
                )
                self._data = defaults
                self._write_to_disk()
                return

            # Mezcla para conservar nuevas claves tras actualizaciones.
            self._data = _deep_merge(defaults, user_data)

    @staticmethod
    def _load_defaults() -> dict[str, Any]:
        """Lee el archivo de configuración por defecto del paquete."""
        if not _DEFAULT_TEMPLATE.exists():
            # fallback: si no existe la plantilla, devolver mínimo viable.
            return {"app": {"version": "1.0.0"}}
        with _DEFAULT_TEMPLATE.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_to_disk(self) -> None:
        """Escribe la configuración actual al disco de forma atómica."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.exception("Could not save configuration to %s", self.path)
            raise SettingsError(str(exc)) from exc

    def save(self) -> None:
        """Guarda la configuración actual al disco."""
        with self._lock:
            self._write_to_disk()

    def reload(self) -> None:
        """Recarga la configuración desde disco."""
        with self._lock:
            self._load()

    # ------------------------------------------------------------------ #
    # Acceso tipo diccionario
    # ------------------------------------------------------------------ #
    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Obtiene un valor mediante una ruta separada por puntos.

        Args:
            dotted_key: Ruta, por ejemplo ``"ui.grid_columns"``.
            default: Valor por defecto si la clave no existe.

        Returns:
            El valor encontrado o ``default``.
        """
        with self._lock:
            current: Any = self._data
            for part in dotted_key.split("."):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return deepcopy(current)

    def set(self, dotted_key: str, value: Any, *, autosave: bool = True) -> None:
        """Establece un valor mediante una ruta separada por puntos.

        Args:
            dotted_key: Ruta, por ejemplo ``"ui.grid_columns"``.
            value: Valor a almacenar. Debe ser serializable en JSON.
            autosave: Si ``True``, guarda en disco automáticamente.
        """
        with self._lock:
            parts = dotted_key.split(".")
            current = self._data
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
            if autosave:
                self._write_to_disk()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._write_to_disk()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    # ------------------------------------------------------------------ #
    # Importar / Exportar
    # ------------------------------------------------------------------ #
    def export_to(self, target: Path | str) -> None:
        """Exporta la configuración actual a un archivo JSON externo.

        Args:
            target: Ruta destino.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with target.open("w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        logger.info("Configuration exported to %s", target)

    def import_from(self, source: Path | str) -> None:
        """Importa configuración desde un archivo JSON externo, fusionándola
        con los valores por defecto.

        Args:
            source: Ruta del archivo a importar.
        """
        source = Path(source)
        try:
            with source.open("r", encoding="utf-8") as handle:
                imported = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise SettingsError(f"No se pudo importar la configuración: {exc}") from exc

        if not isinstance(imported, dict):
            raise SettingsError("El archivo importado no contiene un objeto JSON válido")

        with self._lock:
            defaults = self._load_defaults()
            self._data = _deep_merge(defaults, imported)
            self._write_to_disk()
        logger.info("Configuration imported from %s", source)

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    def expand_path(self, value: str) -> Path:
        """Expande ``~`` y variables de entorno en una ruta de configuración.

        Args:
            value: Cadena con una ruta potencialmente con ``~`` o ``$VAR``.

        Returns:
            Objeto :class:`pathlib.Path` expandido.
        """
        return Path(os.path.expandvars(os.path.expanduser(value)))

    def reset_to_defaults(self) -> None:
        """Restaura la configuración a los valores por defecto del paquete."""
        with self._lock:
            self._data = self._load_defaults()
            self._write_to_disk()
        logger.info("Configuration restored to defaults")

    def backup(self, target: Path | str | None = None) -> Path:
        """Crea una copia de seguridad de la configuración actual.

        Args:
            target: Ruta destino. Si se omite se añade el sufijo ``.bak``.

        Returns:
            Ruta del archivo de respaldo creado.
        """
        target = Path(target) if target else self.path.with_suffix(".json.bak")
        with self._lock:
            shutil.copy2(self.path, target)
        logger.info("Backup created at %s", target)
        return target
