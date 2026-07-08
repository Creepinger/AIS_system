"""经纬度方格图(右侧)。

- 默认 8×8 网格,每格 0.5°
- 以第一条船的位置为中心
- 线性映射经纬度到画布像素
- 船舶按 cog 旋转的小三角
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRectF, QPointF, Slot
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF, QFont
from PySide6.QtWidgets import QWidget

from ais.ais_ship import AIS_Ship


@dataclass
class _Center:
    lat: float = 0.0
    lon: float = 0.0
    span_deg: float = 4.0  # 8 × 0.5°


class GridCanvas(QWidget):
    def __init__(self, grid_size: int = 8, grid_step_deg: float = 0.5,
                 parent=None) -> None:
        super().__init__(parent)
        self.grid_size = grid_size
        self.grid_step = grid_step_deg
        self.span = grid_size * grid_step_deg
        self.center = _Center()
        self.ships: dict[int, AIS_Ship] = {}  # mmsi → ship
        self.setMinimumSize(400, 400)
        self.setAutoFillBackground(False)

    def reset(self) -> None:
        self.ships.clear()
        self.center = _Center()
        self.update()

    @Slot(object)
    def on_ship(self, ship: AIS_Ship) -> None:
        mmsi = ship.mmsi
        # 第一条船时,把它设为地图中心
        if not self.ships:
            self.center.lat = ship.latitude
            self.center.lon = ship.longitude
        self.ships[mmsi] = ship
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 30
        plot_w = w - 2 * margin
        plot_h = h - 2 * margin

        # 背景
        painter.fillRect(self.rect(), QColor("#0b1d2a"))

        # 网格
        pen = QPen(QColor("#224466"), 1)
        painter.setPen(pen)
        for i in range(self.grid_size + 1):
            x = margin + i * plot_w / self.grid_size
            painter.drawLine(int(x), margin, int(x), h - margin)
            y = margin + i * plot_h / self.grid_size
            painter.drawLine(margin, int(y), w - margin, int(y))

        # 经纬度标签
        pen = QPen(QColor("#99ccff"))
        painter.setPen(pen)
        f = QFont()
        f.setPointSize(8)
        painter.setFont(f)
        for i in range(self.grid_size + 1):
            x_frac = (i / self.grid_size) - 0.5
            lon = self.center.lon + x_frac * self.span
            x = margin + i * plot_w / self.grid_size
            painter.drawText(int(x) - 18, h - margin + 18, f"{lon:.2f}")
            y_frac = 0.5 - (i / self.grid_size)
            lat = self.center.lat + y_frac * self.span
            y = margin + i * plot_h / self.grid_size
            painter.drawText(2, int(y) + 4, f"{lat:.2f}")

        # 中心十字
        cx, cy = self._latlon_to_pixel(self.center.lat, self.center.lon, w, h, margin)
        pen = QPen(QColor("#5588aa"), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(cx, margin, cx, h - margin)
        painter.drawLine(margin, cy, w - margin, cy)

        # 船舶
        for ship in self.ships.values():
            self._draw_ship(painter, ship, w, h, margin)

    def _latlon_to_pixel(self, lat: float, lon: float,
                         w: int, h: int, margin: int) -> tuple[int, int]:
        x_frac = (lon - self.center.lon) / self.span + 0.5
        y_frac = 0.5 - (lat - self.center.lat) / self.span
        x = margin + x_frac * (w - 2 * margin)
        y = margin + y_frac * (h - 2 * margin)
        return int(x), int(y)

    def _draw_ship(self, painter: QPainter, ship: AIS_Ship,
                   w: int, h: int, margin: int) -> None:
        try:
            x, y = self._latlon_to_pixel(ship.latitude, ship.longitude, w, h, margin)
        except Exception:
            return
        if not (margin - 5 <= x <= w - margin + 5 and margin - 5 <= y <= h - margin + 5):
            # 船在视图外
            return

        # 三角朝向按 cog 旋转
        cog = ship.cog
        size = 8
        # 默认朝上(0° = 北)
        triangle = QPolygonF([
            QPointF(0, -size),
            QPointF(-size * 0.7, size * 0.7),
            QPointF(size * 0.7, size * 0.7),
        ])
        painter.save()
        painter.translate(x, y)
        painter.rotate(cog)
        painter.setBrush(QBrush(QColor("#ff6644")))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawPolygon(triangle)
        painter.restore()

        # MMSI 标签
        painter.setPen(QPen(QColor("#ffffff")))
        f = QFont()
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(x + 10, y - 6, str(ship.mmsi))