"""asyncio 版数据源。

不依赖 PySide6;与 link/data_source.make_source 接口对齐,但返回的是
async 迭代器(逐行 yield)而非 Qt Signal。

提供:
- `classify_lines(it)` → 在外部按行迭代 NMEA
- `stop_event: asyncio.Event` 用于停止所有源
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

log = logging.getLogger(__name__)

LineCallback = Callable[[str], None]


# ---------------- 文件回放 ----------------
async def replay_file(path: str | Path,
                      line_delay_ms: int = 50,
                      stop_event: Optional[asyncio.Event] = None,
                      on_line: LineCallback = lambda s: None) -> None:
    """异步逐行回放文本文件。

    Args:
        path: 文本文件路径,每行一条 NMEA。
        line_delay_ms: 行间延迟(模拟实时)。
        stop_event: 置位即停止。
        on_line: 收到一条完整 NMEA 行的回调。
    """
    p = Path(path)
    if not p.exists():
        log.error("文件不存在: %s", p)
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        if stop_event is not None and stop_event.is_set():
            break
        line = raw.strip()
        # 接受所有 AIS NMEA 0183 句子。
        # 标准 talker 是 AI(船→站) / AB(基站聚合) / BS / AN / AP / AS 等,
        # 只要消息体以 VDM(船→站) 或 VDO(船→船) 结尾即可。
        if line and line.startswith("!") and (
            "VDM," in line[:8] or "VDO," in line[:8]
        ):
            on_line(line)
        await asyncio.sleep(line_delay_ms / 1000.0)


# ---------------- 串口 ----------------
async def replay_serial(port: str, baudrate: int = 38400,
                        stop_event: Optional[asyncio.Event] = None,
                        on_line: LineCallback = lambda s: None) -> None:
    """从串口读取 NMEA 行(pyserial 在 executor 里读,行交回调)。

    需要 pyserial;否则报 ImportError。
    """
    try:
        import serial
    except ImportError:
        log.error("pyserial 未安装,pip install pyserial")
        return

    loop = asyncio.get_event_loop()

    def _open() -> "serial.Serial":
        return serial.Serial(
            port=port, baudrate=baudrate, bytesize=8,
            parity="N", stopbits=1, timeout=0.5,
        )

    try:
        ser = await loop.run_in_executor(None, _open)
    except Exception as e:
        log.error("打开串口 %s 失败: %s", port, e)
        return

    buffer = ""
    try:
        while stop_event is None or not stop_event.is_set():
            try:
                chunk = await loop.run_in_executor(None, ser.read, 1024)
            except Exception as e:
                log.error("串口读取失败: %s", e)
                break
            if chunk:
                buffer += chunk.decode("ascii", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line and line.startswith("!"):
                        on_line(line)
    finally:
        ser.close()


# ---------------- TCP 网口 ----------------
async def replay_net(host: str, port: int,
                     stop_event: Optional[asyncio.Event] = None,
                     reconnect_sec: float = 3.0,
                     on_line: LineCallback = lambda s: None) -> None:
    """从 TCP 接收 NMEA 行(断线自动重连)。"""
    buffer = ""
    while stop_event is None or not stop_event.is_set():
        try:
            reader, writer = await asyncio.open_connection(host, port)
        except OSError as e:
            log.warning("连接 %s:%d 失败: %s; %.1fs 后重试",
                        host, port, e, reconnect_sec)
            try:
                await asyncio.sleep(reconnect_sec)
            except asyncio.CancelledError:
                break
            continue
        log.info("已连接 %s:%d", host, port)
        try:
            while stop_event is None or not stop_event.is_set():
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if not data:
                    break
                buffer += data.decode("ascii", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line and line.startswith("!"):
                        on_line(line)
        except OSError as e:
            log.warning("连接断开: %s", e)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


# ---------------- 工厂函数 ----------------
async def start_source(kind: str, *,
                       on_line: LineCallback,
                       stop_event: asyncio.Event,
                       path: Optional[str] = None,
                       serial_port: Optional[str] = None,
                       baudrate: int = 38400,
                       host: str = "127.0.0.1",
                       port: int = 5000,
                       line_delay_ms: int = 50) -> asyncio.Task:
    """启动数据源任务,返回 asyncio.Task(可用 task.cancel() 停止)。"""
    if kind == "file":
        return asyncio.create_task(
            replay_file(path or "", line_delay_ms, stop_event, on_line)
        )
    if kind == "serial":
        return asyncio.create_task(
            replay_serial(serial_port or "COM3", baudrate, stop_event, on_line)
        )
    if kind == "net":
        return asyncio.create_task(
            replay_net(host, port, stop_event, on_line=on_line)
        )
    raise ValueError(f"unknown source: {kind}")
