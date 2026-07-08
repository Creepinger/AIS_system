"""解码服务:数据源 → 协议解析 → 增量船舶表 / 统计。

单例,FastAPI lifespan 启停。

主循环:
  1. 从 link_async 收 NMEA 行(在后台 task 中调用 on_line)
  2. bcc_check → parse_line → FragmentBuffer.feed → decode_ais
  3. 写入 self.ships[mmsi] 与 self.stats
  4. 后台 _broadcast_loop 每 200ms 把当前快照推给 WS 客户端
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from ais.ais_ship import AIS_Ship
from ais.bcc import bcc_check
from ais.decoder import FragmentBuffer, decode_ais
from ais.nmea import parse_line

from config import CONFIG, PROJECT_ROOT
from web.link_async import start_source

log = logging.getLogger(__name__)


class AISService:
    def __init__(self) -> None:
        self.frag = FragmentBuffer()
        self.stats: dict = {
            "rx": 0, "bcc_pass": 0, "bcc_fail": 0,
            "decoded": 0, "by_type": {},
            "started_at": time.time(),
        }
        # 当前活跃数据源描述,供前端显示
        self.source_desc: str = "未连接"
        # 每艘船的最新一次解码结果
        self.ships: dict[int, dict] = {}
        # 暂停状态
        self.paused: bool = False
        # 待广播的帧(增量);每 200ms 推一次
        self._pending_batch: list[dict] = []
        self._pending_updated_mmsi: set[int] = set()
        # 锁:防止 on_line 与 broadcast_loop 并发修改 self.ships
        self._lock = asyncio.Lock()
        # 当前数据源 task
        self._source_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._broadcaster: Optional[asyncio.Task] = None
        # 命令队列:WebSocket 命令处理
        self._cmd_queue: asyncio.Queue = asyncio.Queue()
        self._current_kind: Optional[str] = None
        self._current_kwargs: dict = {}

    # ---------- 生命周期 ----------
    async def start(self, kind: str = "file", **kwargs) -> None:
        if self._broadcaster is None:
            self._broadcaster = asyncio.create_task(self._broadcast_loop())
        await self._switch_source(kind, **kwargs)

    async def stop(self) -> None:
        if self._source_task is not None:
            self._stop_event.set() if self._stop_event else None
            self._source_task.cancel()
            try:
                await self._source_task
            except (asyncio.CancelledError, Exception):
                pass
            self._source_task = None
        if self._broadcaster is not None:
            self._broadcaster.cancel()
            try:
                await self._broadcaster
            except (asyncio.CancelledError, Exception):
                pass
            self._broadcaster = None

    async def _switch_source(self, kind: str, **kwargs) -> None:
        # 先停旧源
        if self._source_task is not None:
            self._stop_event.set() if self._stop_event else None
            self._source_task.cancel()
            try:
                await self._source_task
            except (asyncio.CancelledError, Exception):
                pass
        self._stop_event = asyncio.Event()
        if kind == "file":
            path = kwargs.get("path") or str(
                PROJECT_ROOT / "tests" / "samples" / "sample_nmea.txt"
            )
            self.source_desc = f"文件: {path}"
            self._source_task = await start_source(
                "file", on_line=self._on_line,
                stop_event=self._stop_event, path=path,
                line_delay_ms=kwargs.get("line_delay_ms", 50),
            )
        elif kind == "net":
            # 支持两种传参方式:
            #   { host, port }       — 直接传(优先)
            #   { path: "IP:PORT" }  — 从文本框传 "IP:PORT" 格式
            raw = kwargs.get("host") or kwargs.get("path") or ""
            if ":" in raw:
                host, _, port_str = raw.partition(":")
                try:
                    port = int(port_str)
                except ValueError:
                    port = 5000
            else:
                host = raw or "127.0.0.1"
                port = 5000
            self.source_desc = f"网口: {host}:{port}"
            self._source_task = await start_source(
                "net", on_line=self._on_line,
                stop_event=self._stop_event, host=host, port=port,
            )
        else:
            raise ValueError(f"unknown source: {kind}")
        self._current_kind = kind
        self._current_kwargs = kwargs

    # ---------- 数据接收回调 ----------
    def _on_line(self, line: str) -> None:
        """从 link_async 在后台 task 中调用(非 async)。

        因为 on_line 是普通函数,我们用 call_soon_threadsafe 把
        处理任务排到事件循环,避免跨线程访问 self.ships。
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 在 executor 线程里没有运行中的 loop,用 _call_soon_threadsafe 是没有 loop 的场景
            # 实际调用方(replay_*)都在 asyncio 任务里,所以一定有 loop
            return
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_line, line)

    def _handle_line(self, line: str) -> None:
        """同步处理一行 NMEA(在事件循环线程里执行)。"""
        if self.paused:
            return
        self.stats["rx"] += 1
        if not bcc_check(line):
            self.stats["bcc_fail"] += 1
            return
        self.stats["bcc_pass"] += 1
        sent = parse_line(line)
        if sent is None:
            return
        payload = self.frag.feed(sent)
        if payload is None:
            return
        ship = AIS_Ship()
        rc = decode_ais(payload, ship)
        if rc != 0:
            return
        self.stats["decoded"] += 1
        self.stats["by_type"][ship.msg_type] = (
            self.stats["by_type"].get(ship.msg_type, 0) + 1
        )
        record = ship.to_dict()
        # 简易的同步更新(ships 在 broadcast_loop 也会读,但同一线程)
        self.ships[ship.mmsi] = record
        self._pending_updated_mmsi.add(ship.mmsi)

    # ---------- 后台广播循环 ----------
    async def _broadcast_loop(self) -> None:
        interval = CONFIG.web.broadcast_interval_ms / 1000.0
        while True:
            await asyncio.sleep(interval)
            await self._flush_once()

    async def _flush_once(self) -> None:
        """构造一帧并推给所有 WS 客户端。"""
        from web.ws import manager
        # 拷贝当前快照与统计
        if self.paused:
            # 暂停时仍可广播状态/源变化,但不重复刷新船舶
            ships_snapshot = []
        else:
            ships_snapshot = list(self.ships.values())
        payload = {
            "type": "batch",
            "ts": time.time(),
            "source": self.source_desc,
            "paused": self.paused,
            "stats": self._stats_view(),
            "ships": ships_snapshot,
        }
        await manager.broadcast(payload)

    def _stats_view(self) -> dict:
        # 计算运行时长
        return {
            **self.stats,
            "ship_count": len(self.ships),
            "uptime_sec": int(time.time() - self.stats["started_at"]),
        }

    # ---------- 命令通道 ----------
    async def handle_command(self, msg: dict) -> None:
        cmd = msg.get("cmd")
        if cmd == "pause":
            self.paused = True
        elif cmd == "resume":
            self.paused = False
        elif cmd == "clear":
            self.ships.clear()
            self.frag = FragmentBuffer()
        elif cmd == "set_source":
            kind = msg.get("kind", "file")
            kwargs = {k: v for k, v in msg.items() if k not in ("cmd", "kind")}
            await self._switch_source(kind, **kwargs)


# 单例
service = AISService()
