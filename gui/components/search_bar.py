"""
Search Bar
==========

Barra de búsqueda con icono y botón de limpiar.

Emite señales cuando cambia el texto o se pulsa Enter.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLineEdit

from gui.theme import load_svg_icon


class SearchBar(QLineEdit):
    """Campo de búsqueda con debounce y botón de limpiar.

    Signals:
        text_changed: Emitida tras un breve debounce cuando cambia el texto.
        submitted: Emitida al pulsar Enter.
    """

    text_changed = Signal(str)
    submitted = Signal(str)

    def __init__(self, parent=None, placeholder: str = "Buscar wallpapers…") -> None:
        super().__init__(parent)
        self.setObjectName("SearchField")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)

        # Icono de búsqueda a la izquierda.
        self._search_action = QAction(self)
        self._search_action.setIcon(load_svg_icon("search", color="#565f89", size=18))
        self.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)

        # Debounce para no emitir en cada tecla.
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._emit_text_changed)

        self.textEdited.connect(self._on_text_edited)
        self.returnPressed.connect(self._on_return_pressed)

    def _on_text_edited(self, _text: str) -> None:
        """Reinicia el debounce al editar el texto."""
        self._debounce_timer.start()

    def _on_return_pressed(self) -> None:
        """Emite la señal submitted con el texto actual."""
        self._debounce_timer.stop()
        self.submitted.emit(self.text().strip())
        self.text_changed.emit(self.text().strip())

    def _emit_text_changed(self) -> None:
        """Emite text_changed tras el debounce."""
        self.text_changed.emit(self.text().strip())

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        self.text_changed.emit("")
