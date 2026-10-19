"""Theme-aware monochrome icons drawn with QPainter (no image files)."""

from __future__ import annotations

import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

_GRID = 24.0
_SCALE = 2  # Render at 2x so icons stay crisp on HiDPI screens.


def _speaker(painter: QPainter) -> None:
    painter.drawPolygon(
        QPolygonF(
            [QPointF(4, 9.5), QPointF(8, 9.5), QPointF(13, 5), QPointF(13, 19), QPointF(8, 14.5), QPointF(4, 14.5)]
        )
    )


def _draw_play(p: QPainter) -> None:
    p.drawPolygon(QPolygonF([QPointF(7, 4.5), QPointF(19, 12), QPointF(7, 19.5)]))


def _draw_stop(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2)


def _draw_retry(p: QPainter) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    # Open circle (arc) with an arrow head at its end.
    p.drawArc(QRectF(5, 5, 14, 14), 60 * 16, 280 * 16)
    p.setBrush(p.pen().color())
    p.drawPolygon(QPolygonF([QPointF(15.5, 2.5), QPointF(19.5, 7.5), QPointF(13, 8)]))


def _draw_volume(p: QPainter) -> None:
    _speaker(p)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(10, 8, 7, 8), -60 * 16, 120 * 16)
    p.drawArc(QRectF(8, 4.5, 13, 15), -60 * 16, 120 * 16)


def _draw_volume_muted(p: QPainter) -> None:
    _speaker(p)
    p.drawLine(QPointF(16, 9.5), QPointF(21, 14.5))
    p.drawLine(QPointF(21, 9.5), QPointF(16, 14.5))


def _star_polygon() -> QPolygonF:
    points = []
    for i in range(10):
        radius = 8.5 if i % 2 == 0 else 3.6
        angle = -math.pi / 2 + i * math.pi / 5
        points.append(QPointF(12 + radius * math.cos(angle), 12.6 + radius * math.sin(angle)))
    return QPolygonF(points)


def _draw_star(p: QPainter) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolygon(_star_polygon())


def _draw_star_filled(p: QPainter) -> None:
    p.drawPolygon(_star_polygon())


def _draw_fullscreen(p: QPainter) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = 4.5 if sx > 0 else 19.5
        cy = 4.5 if sy > 0 else 19.5
        p.drawLine(QPointF(cx, cy), QPointF(cx + 5 * sx, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + 5 * sy))


def _draw_copy(p: QPainter) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(9, 9, 10, 10), 2, 2)
    p.drawPolyline(
        QPolygonF(
            [
                QPointF(15, 6),
                QPointF(15, 5),
                QPointF(6, 5),
                QPointF(5, 6),
                QPointF(5, 15),
                QPointF(6, 15),
                QPointF(9, 15),
            ]
        )
    )


def _draw_info(p: QPainter) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(4, 4, 16, 16))
    p.drawLine(QPointF(12, 11), QPointF(12, 16))
    p.setBrush(p.pen().color())
    p.drawEllipse(QRectF(11.1, 7.1, 1.8, 1.8))


def _draw_sources(p: QPainter) -> None:
    for y in (7, 12, 17):
        p.drawLine(QPointF(9.5, y), QPointF(19.5, y))
        p.setBrush(p.pen().color())
        p.drawEllipse(QRectF(4.5, y - 1.2, 2.4, 2.4))


# name -> (draw function, filled). Filled shapes use the colour as brush and pen.
_DRAWERS: dict[str, tuple[Callable[[QPainter], None], bool]] = {
    "play": (_draw_play, True),
    "stop": (_draw_stop, True),
    "retry": (_draw_retry, False),
    "volume": (_draw_volume, True),
    "volume-muted": (_draw_volume_muted, True),
    "star": (_draw_star, False),
    "star-filled": (_draw_star_filled, True),
    "fullscreen": (_draw_fullscreen, False),
    "copy": (_draw_copy, False),
    "info": (_draw_info, False),
    "sources": (_draw_sources, False),
}

ICON_NAMES: tuple[str, ...] = tuple(_DRAWERS)


def _render(name: str, color: QColor, size: int) -> QPixmap:
    draw, filled = _DRAWERS[name]
    pixmap = QPixmap(size * _SCALE, size * _SCALE)
    pixmap.setDevicePixelRatio(_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / _GRID, size / _GRID)
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(color if filled else Qt.BrushStyle.NoBrush)
        draw(painter)
    finally:
        painter.end()
    return pixmap


def make_icon(name: str, color: QColor, size: int = 18, disabled_color: QColor | None = None) -> QIcon:
    """Return a ``QIcon`` for ``name`` drawn in ``color``; raise ``KeyError`` for unknown names."""
    if name not in _DRAWERS:
        raise KeyError(name)
    icon = QIcon()
    icon.addPixmap(_render(name, color, size), QIcon.Mode.Normal)
    if disabled_color is not None:
        icon.addPixmap(_render(name, disabled_color, size), QIcon.Mode.Disabled)
    return icon
