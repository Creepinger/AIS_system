"""TCP 网口数据源(默认连接 127.0.0.1:5000)。

支持断线自动重连。
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .data_source import DataSource


class NetworkReader(DataSource):
    def __init__(self, host: str = "127.0.0.1", port: int = 5000,
                 reconnect_sec: float = 3.0, parent=None) -> None:
        super().__init__(f"net:{host}:{port}", parent)
        self.host = host
        self.port = port
        self.reconnect_sec = reconnect_sec
        self._thread: _NetThread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._thread = _NetThread(self.host, self.port, self.reconnect_sec)
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
        self.status.emit("网口已停止")


class _NetThread(QThread):
    line = Signal(str)
    status_msg = Signal(str)
    err_msg = Signal(str)

    def __init__(self, host: str, port: int, reconnect_sec: float) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.reconnect_sec = reconnect_sec
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        import socket
        buffer = ""
        while not self._stop_flag:
            try:
                self.status_msg.emit(f"连接 {self.host}:{self.port} ...")
                sock = socket.create_connection((self.host, self.port), timeout=3)
                sock.settimeout(1.0)
                self.status_msg.emit(f"已连接 {self.host}:{self.port}")
                while not self._stop_flag:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError as e:
                        self.err_msg.emit(f"连接断开: {e}")
                        break
                    if not chunk:
                        break
                    buffer += chunk.decode("ascii", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line and line.startswith("!"):
                            self.line.emit(line)
                sock.close()
            except OSError as e:
                self.err_msg.emit(f"网络错误: {e}; {self.reconnect_sec}s 后重试")
            if not self._stop_flag:
                self.msleep(int(self.reconnect_sec * 1000))
        self.status_msg.emit("网口已停止")