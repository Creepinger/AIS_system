"""串口数据源(pyserial + QThread)。

默认参数 38400 8N1,与 AIS VHF 数据链路标准匹配。
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .data_source import DataSource


class SerialReader(DataSource):
    def __init__(self, port: str, baudrate: int = 38400,
                 bytesize: int = 8, parity: str = "N", stopbits: float = 1,
                 parent=None) -> None:
        super().__init__(f"serial:{port}@{baudrate}", parent)
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self._thread: _SerialThread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._thread = _SerialThread(
            self.port, self.baudrate, self.bytesize, self.parity, self.stopbits,
        )
        self._thread.line.connect(self.lines.emit)
        self._thread.status_msg.connect(self.status.emit)
        self._thread.err_msg.connect(self.error.emit)
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread.wait(2000)
            self._thread = None
        self._running = False
        self.status.emit("串口已停止")


class _SerialThread(QThread):
    line = Signal(str)
    status_msg = Signal(str)
    err_msg = Signal(str)

    def __init__(self, port: str, baudrate: int, bytesize: int,
                 parity: str, stopbits: float) -> None:
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        try:
            import serial
        except ImportError:
            self.err_msg.emit("pyserial 未安装,pip install pyserial")
            return
        try:
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=0.5,
            )
        except Exception as e:
            self.err_msg.emit(f"打开串口 {self.port} 失败: {e}")
            return

        self.status_msg.emit(f"已连接 {self.port} @ {self.baudrate}")
        buffer = ""
        try:
            while not self._stop_flag:
                try:
                    chunk = ser.read(1024)
                except Exception as e:
                    self.err_msg.emit(f"读取失败: {e}")
                    break
                if chunk:
                    try:
                        text = chunk.decode("ascii", errors="ignore")
                    except UnicodeDecodeError:
                        text = ""
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line and line.startswith("!"):
                            self.line.emit(line)
        finally:
            ser.close()
            self.status_msg.emit("串口已关闭")