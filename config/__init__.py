"""
Config
======

Paquete encargado de la gestión de configuración persistente de la aplicación.

Proporciona la clase :class:`Settings` que carga, guarda y expone de manera
tipada todas las preferencias del usuario, así como un esquema de configuración
por defecto basado en JSON.
"""

from config.settings import Settings, SettingsError, DEFAULT_CONFIG_PATH

__all__ = ["Settings", "SettingsError", "DEFAULT_CONFIG_PATH"]
