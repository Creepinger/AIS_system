"""原始报文存档器。

所有从数据源接收到的 NMEA 行(无论 BCC 是否通过)都实时写入 `raw_log.txt`,
便于事后审计与回放。
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from PySide6.QtCore import QObject, Slot


class RawLogger(QObject):
    def __init__(self, path: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    @Slot(str)
    def write(self, line: str) -> None:
        ts = _dt.datetime.utcnow().isoformat(timespec="seconds")
        self._fh.write(f"{ts}Z {line}\n")

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()


class ResultLogger(QObject):
    """解析结果存档:格式 `时间戳|MMSI|经度|纬度|航速|航向|船名`。"""

    def __init__(self, path: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    @Slot(object)
    def write(self, ship) -> None:
        ts = _dt.datetime.utcnow().isoformat(timespec="seconds")
        line = (
            f"{ts}Z|{ship.mmsi}|{ship.latitude:.5f}|{ship.longitude:.5f}"
            f"|{ship.sog:.1f}|{ship.cog}|{ship.shipname or ''}|type={ship.msg_type}\n"
        )
        self._fh.write(line)

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()