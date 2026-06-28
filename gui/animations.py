"""
Animations
==========

Animaciones suaves reutilizables para la GUI.

Usa :class:`QPropertyAnimation` y :class:`QParallelAnimationGroup` para
animar propiedades de los widgets (opacidad, posición, escala).
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

logger = logging.getLogger(__name__)

# Duraciones por defecto (ms).
DURATION_FAST: int = 150
DURATION_NORMAL: int = 250
DURATION_SLOW: int = 400


def fade_in(widget: QWidget, duration: int = DURATION_NORMAL) -> QPropertyAnimation:
    """Animación de aparición (fade in).

    Args:
        widget: Widget a animar.
        duration: Duración en milisegundos.

    Returns:
        La animación creada (ya iniciada).
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out(widget: QWidget, duration: int = DURATION_NORMAL,
             hide_on_finish: bool = True) -> QPropertyAnimation:
    """Animación de desaparición (fade out).

    Args:
        widget: Widget a animar.
        duration: Duración en milisegundos.
        hide_on_finish: Si ``True``, oculta el widget al terminar.
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    if hide_on_finish:
        anim.finished.connect(widget.hide)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def slide_in(
    widget: QWidget,
    *,
    direction: Qt.Orientation = Qt.Orientation.Horizontal,
    distance: int = 30,
    duration: int = DURATION_NORMAL,
) -> QPropertyAnimation:
    """Desliza un widget desde un lateral.

    Args:
        widget: Widget a animar.
        direction: Horizontal (X) o Vertical (Y).
        distance: Desplazamiento en píxeles.
        duration: Duración en milisegundos.
    """
    prop = b"pos" if direction == Qt.Orientation.Horizontal else b"y"
    start = widget.pos()
    if direction == Qt.Orientation.Horizontal:
        end = start.__class__(start.x() - distance, start.y())  # type: ignore[arg-type]
        # Corrección: QPoint admite constructor (x, y)
        from PySide6.QtCore import QPoint

        end = QPoint(start.x() + distance, start.y())
        anim = QPropertyAnimation(widget, b"pos", widget)
        anim.setStartValue(QPoint(start.x() - distance, start.y()))
        anim.setEndValue(start)
    else:
        from PySide6.QtCore import QPoint

        anim = QPropertyAnimation(widget, b"pos", widget)
        anim.setStartValue(QPoint(start.x(), start.y() - distance))
        anim.setEndValue(start)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def pulse(widget: QWidget, color: str = "#7aa2f7",
          duration: int = DURATION_NORMAL) -> None:
    """Efecto de pulso: cambia temporalmente la hoja de estilo.

    Args:
        widget: Widget a animar.
        color: Color del pulso.
        duration: Duración del efecto.
    """
    original = widget.styleSheet()
    widget.setStyleSheet(
        f"background-color: {color}; border-radius: 6px;"
    )
    QTimer.singleShot(duration, lambda: widget.setStyleSheet(original))


def animate_property(
    target: QObject,
    property_name: bytes,
    start: Any,
    end: Any,
    *,
    duration: int = DURATION_NORMAL,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
) -> QPropertyAnimation:
    """Atajo para animar cualquier propiedad numérica.

    Args:
        target: Objeto destino.
        property_name: Nombre de la propiedad (bytes).
        start: Valor inicial.
        end: Valor final.
        duration: Duración en ms.
        easing: Curva de easing.

    Returns:
        Animación iniciada.
    """
    anim = QPropertyAnimation(target, property_name, target)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def color_to_qcolor(color: str) -> QColor:
    """Convierte ``#RRGGBB`` o ``#AARRGGBB`` a :class:`QColor`."""
    return QColor(color)
