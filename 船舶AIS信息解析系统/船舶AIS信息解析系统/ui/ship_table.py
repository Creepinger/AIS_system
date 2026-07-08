"""船舶信息表格(左侧)。"""
from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

from ais.ais_ship import AIS_Ship


HEADERS = ["MMSI", "纬度", "经度", "航速(节)", "航向(°)", "船名", "UTC(s)", "类型"]


class ShipTable(QTableWidget):
    def __init__(self, max_rows: int = 500, parent=None) -> None:
        super().__init__(0, len(HEADERS), parent)
        self._max_rows = max_rows
        self.setHorizontalHeaderLabels(HEADERS)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)

        # MMSI → row 索引,用于滚动更新同一艘船
        self._index: dict[int, int] = OrderedDict()

    @Slot(object)
    def on_ship(self, ship: AIS_Ship) -> None:
        mmsi = ship.mmsi
        row = self._index.get(mmsi)
        if row is None:
            row = self.rowCount()
            if row >= self._max_rows:
                # 移除最早一行(FIFO)
                self.removeRow(0)
                self._index = OrderedDict(
                    (k, v - 1) for k, v in self._index.items()
                )
                row = self.rowCount()
            self.insertRow(row)
            self._index[mmsi] = row
        # 写入单元格
        values = ship.to_row()
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            if col == 0:
                item.setData(Qt.UserRole, mmsi)
            self.setItem(row, col, item)

    def clear_all(self) -> None:
        self.setRowCount(0)
        self._index.clear()