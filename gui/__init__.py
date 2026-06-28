"""
GUI
===

Interfaz gráfica de Wallpaper Manager construida con PySide6 (Qt6).

La interfaz está organizada en:

* :mod:`gui.theme` — carga de la hoja de estilos y utilidades de iconos.
* :mod:`gui.animations` — animaciones suaves reutilizables.
* :mod:`gui.components` — widgets reutilizables (tarjetas, búsqueda, menús).
* :mod:`gui.sidebar` — barra lateral de navegación.
* :mod:`gui.wallpaper_grid` — cuadrícula principal de miniaturas.
* :mod:`gui.preview_panel` — panel de vista previa y controles.
* :mod:`gui.settings_dialog` — diálogo de configuración.
* :mod:`gui.main_window` — ventana principal.
"""

from gui.main_window import MainWindow

__all__ = ["MainWindow"]
