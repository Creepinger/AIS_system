"""数据源抽象基类。

所有数据源(串口/网口/文件)统一暴露:
- `lines: Signal(str)`:每条 NMEA 行
- `start()` / `stop()`:生命周期管理
- `is_running: bool`
"""
from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import QObject, Signal


class DataSource(QObject):
    """AIS 数据源抽象类。"""

    lines = Signal(str)            # 一条 NMEA 行(含 `!AIVDM...*xx`)
    status = Signal(str)           # 状态变化文本
    error = Signal(str)            # 错误信息

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


def make_source(kind: str, **kwargs) -> DataSource:
    """工厂方法。

    Args:
        kind: "file" | "serial" | "net"
        kwargs: 透传给具体数据源
    """
    if kind == "file":
        from .file_replay import FileReplay
        return FileReplay(path=kwargs.get("path", ""),
                          line_delay_ms=kwargs.get("line_delay_ms", 50))
    if kind == "serial":
        from .serial_reader import SerialReader
        return SerialReader(port=kwargs.get("port", "COM3"),
                            baudrate=kwargs.get("baudrate", 38400))
    if kind == "net":
        from .network_reader import NetworkReader
        return NetworkReader(host=kwargs.get("host", "127.0.0.1"),
                             port=kwargs.get("port", 5000))
    raise ValueError(f"unknown source kind: {kind}")