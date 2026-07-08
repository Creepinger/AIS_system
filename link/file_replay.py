"""文件回放数据源。

按行读取 .txt,每行延迟 line_delay_ms 毫秒发出。
便于无实验室设备时调试解码与 UI。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread

from .data_source import DataSource


class FileReplay(DataSource):
    def __init__(self, path: str, line_delay_ms: int = 50,
                 parent=None) -> None:
        super().__init__(f"file:{path}", parent)
        self.path = Path(path)
        self.line_delay_ms = line_delay_ms
        self._thread: _ReplayThread | None = None

    def start(self) -> None:
        if self._running:
            return
        if not self.path.exists():
            self.error.emit(f"sample file not found: {self.path}")
            return
        self._thread = _ReplayThread(self.path, self.line_delay_ms)
        self._thread.line.connect(self.lines.emit)
        self._thread.start()
        self._running = True
        self.status.emit(f"回放中: {self.path}")

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
            self._thread.wait(2000)
            self._thread = None
        self._running = False
        self.status.emit("回放已停止")


class _ReplayThread(QThread):
    from PySide6.QtCore import Signal
    line = Signal(str)

    def __init__(self, path: Path, delay_ms: int) -> None:
        super().__init__()
        self.path = path
        self.delay_ms = delay_ms
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.line.emit(f"!ERROR,{e}")
            return
        for raw in text.splitlines():
            if self._stop_flag:
                break
            line = raw.strip()
            if line and (line.startswith("!AIVDM") or line.startswith("!AIVDO")):
                self.line.emit(line)
            self.msleep(self.delay_ms)