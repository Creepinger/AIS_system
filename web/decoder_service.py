"""解码服务:数据源 → 协议解析 → 增量船舶表 / 统计。

单例,FastAPI lifespan 启停。

支持双解码器模式:
- 自研解析器 (custom): 基于 ITU-R M.1371 协议的自实现
- pyais 库 (pyais): 第三方开源库
- 对比模式 (compare): 同时运行两种解码器，对比结果

主循环:
  1. 从 link_async 收 NMEA 行(在后台 task 中调用 on_line)
  2. BCC 校验 + NMEA 解析
  3. 根据解码器模式选择处理方式:
     - custom: 自研 decode_ais
     - pyais: pyais 库解码
     - compare: 两种都跑，对比结果
  4. 写入 self.ships[mmsi] 与 self.stats
  5. 后台 _broadcast_loop 每 200ms 把当前快照推给 WS 客户端
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from ais.ais_ship import AIS_Ship
from ais.bcc import bcc_check
from ais.decoder import FragmentBuffer, decode_ais
from ais.nmea import parse_line
from ais.unified_decoder import UnifiedDecoder, DecoderType

from config import CONFIG, PROJECT_ROOT
from web.link_async import start_source
from storage.fastapi_store import FastSqliteStore

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
        # 线程锁:用于同步访问共享数据(兼容同步回调)
        self._thread_lock = threading.Lock()
        # 当前数据源 task
        self._source_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._broadcaster: Optional[asyncio.Task] = None
        # 命令队列:WebSocket 命令处理
        self._cmd_queue: asyncio.Queue = asyncio.Queue()
        self._current_kind: Optional[str] = None
        self._current_kwargs: dict = {}

        # 解码器相关
        # 解码模式: custom (自研) / pyais / compare (对比)
        self._decoder_mode: str = "custom"
        self._unified_decoder: UnifiedDecoder = UnifiedDecoder(DecoderType.CUSTOM)
        # 对比结果缓存 (最近 N 条)
        self._comparison_results: list[dict] = []
        self._max_comparison_results: int = 100

        # 船舶过期清理
        self._max_ship_age_sec: int = 60
        self._last_cleanup_time: float = time.time()
        # 数据库持久化
        self._store: Optional[FastSqliteStore] = None

    # ---------- 生命周期 ----------
    async def start(self, kind: str = "file", **kwargs) -> None:
        if CONFIG.db.enabled:
            self._store = FastSqliteStore(CONFIG.db.sqlite_path)
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
        if self._store is not None:
            self._store.close()
            self._store = None

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
            path = kwargs.get("path") or CONFIG.file.path
            self.source_desc = f"文件: {path}"
            self._source_task = await start_source(
                "file", on_line=self._on_line,
                stop_event=self._stop_event, path=path,
                line_delay_ms=kwargs.get("line_delay_ms", 50),
            )
        elif kind == "serial":
            port = kwargs.get("serial_port") or kwargs.get("path") or CONFIG.serial.port
            baudrate = kwargs.get("baudrate", CONFIG.serial.baudrate)
            self.source_desc = f"串口: {port} @ {baudrate}"
            self._source_task = await start_source(
                "serial", on_line=self._on_line,
                stop_event=self._stop_event, serial_port=port, baudrate=baudrate,
            )
        elif kind == "net":
            # 优先使用前端独立发送的 host/port 字段;
            # 兼容旧的 "host:port" 单字符串形式。
            host = kwargs.get("host")
            port = kwargs.get("port")
            if not host and kwargs.get("path"):
                raw = kwargs["path"]
                if ":" in raw:
                    host, _, port_str = raw.partition(":")
                    if port is None:
                        try:
                            port = int(port_str)
                        except (ValueError, TypeError):
                            port = None
                else:
                    host = raw
            if not host:
                host = CONFIG.network.host
            if port is None:
                try:
                    port = int(port)
                except (TypeError, ValueError):
                    port = CONFIG.network.port
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
        """从 link_async 在后台 task 中调用(非 async)。"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            log.warning("无法获取事件循环，数据可能丢失")
            return
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_line, line)
        else:
            log.warning("事件循环未运行，数据可能丢失")

    def _handle_line(self, line: str) -> None:
        """同步处理一行 NMEA(在事件循环线程里执行)。"""
        try:
            if self.paused:
                return
            with self._thread_lock:
                self.stats["rx"] += 1
            if not bcc_check(line):
                with self._thread_lock:
                    self.stats["bcc_fail"] += 1
                log.warning("BCC 校验失败，丢弃脏数据: %s", line[:60])
                return
            with self._thread_lock:
                self.stats["bcc_pass"] += 1

            if self._decoder_mode == "compare":
                self._handle_line_compare(line)
            elif self._decoder_mode == "pyais":
                self._handle_line_pyais(line)
            else:
                self._handle_line_custom(line)
        except Exception as e:
            log.error("处理 NMEA 行时发生异常: %s, 行: %s", e, line[:60])

    async def _async_handle_line(self, line: str) -> None:
        """异步处理一行 NMEA(带锁保护)。"""
        async with self._lock:
            self._handle_line(line)

    def _handle_line_custom(self, line: str) -> None:
        """使用自研解析器处理一行 NMEA。"""
        try:
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
            self._update_ship(ship)
        except Exception as e:
            log.error("自研解码器处理失败: %s", e)

    def _handle_line_pyais(self, line: str) -> None:
        """使用 pyais 库处理一行 NMEA。"""
        try:
            from ais.pyais_decoder import PyAISDecoder
            decoder = PyAISDecoder()
            ship = AIS_Ship()
            rc = decoder.decode_nmea(line, ship)
            if rc != 0:
                return
            self._update_ship(ship)
        except Exception as e:
            log.error("pyais 解码器处理失败: %s", e)

    def _handle_line_compare(self, line: str) -> None:
        """对比模式：同时使用两种解码器，记录对比结果。"""
        try:
            result = self._unified_decoder.decode_and_compare(line)

            # 记录对比结果（只要有 pyais 结果就记录）
            if result.pyais_dict and result.pyais_dict.get("mmsi"):
                compare_dict = result.to_dict()
                with self._thread_lock:
                    self._comparison_results.append(compare_dict)
                    if len(self._comparison_results) > self._max_comparison_results:
                        self._comparison_results.pop(0)

            # 使用自研结果更新船舶
            if result.custom_ship:
                self._update_ship(result.custom_ship)
        except Exception as e:
            log.error("对比模式处理失败: %s", e)

    def _update_ship(self, ship: AIS_Ship) -> None:
        """更新船舶数据。"""
        try:
            record = ship.to_dict()
            record["_ts"] = time.time()
            with self._thread_lock:
                self.stats["decoded"] += 1
                self.stats["by_type"][ship.msg_type] = (
                    self.stats["by_type"].get(ship.msg_type, 0) + 1
                )
                self.ships[ship.mmsi] = record
            if self._store is not None:
                self._store.insert(ship)
        except Exception as e:
            log.error("更新船舶数据失败: %s", e)

    def _cleanup_expired_ships(self) -> None:
        """清理过期船舶(超过 _max_ship_age_sec 未更新)。"""
        now = time.time()
        if now - self._last_cleanup_time < 10:
            return
        self._last_cleanup_time = now

        expired_mmsis = []
        with self._thread_lock:
            for mmsi, record in self.ships.items():
                if now - record.get("_ts", 0) > self._max_ship_age_sec:
                    expired_mmsis.append(mmsi)
            for mmsi in expired_mmsis:
                del self.ships[mmsi]

    # ---------- 后台广播循环 ----------
    async def _broadcast_loop(self) -> None:
        interval = CONFIG.web.broadcast_interval_ms / 1000.0
        while True:
            await asyncio.sleep(interval)
            await self._flush_once()

    async def _flush_once(self) -> None:
        """构造一帧并推给所有 WS 客户端。"""
        from web.ws import manager
        self._cleanup_expired_ships()
        with self._thread_lock:
            if self.paused:
                ships_snapshot = []
            else:
                ships_snapshot = list(self.ships.values())
            stats_view = self._stats_view()
            source_desc = self.source_desc
            paused = self.paused
            decoder_mode = self._decoder_mode
            comparison_results = self._comparison_results[-10:] if self._decoder_mode == "compare" and self._comparison_results else []

        payload = {
            "type": "batch",
            "ts": time.time(),
            "source": source_desc,
            "paused": paused,
            "stats": stats_view,
            "ships": ships_snapshot,
            "decoder_mode": decoder_mode,
        }

        if comparison_results:
            payload["comparison"] = comparison_results

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
            # 清空所有船舶 / 片段 / 对比结果, 同时重置统计数据
            # (收包 / BCC / 解码 / 类型计数), 并自动暂停接收新数据
            # (符合 UI 上"清空"= 重置视图并冻结)。
            self.ships.clear()
            self.frag = FragmentBuffer()
            self._comparison_results.clear()
            with self._thread_lock:
                self.stats["rx"] = 0
                self.stats["bcc_pass"] = 0
                self.stats["bcc_fail"] = 0
                self.stats["decoded"] = 0
                self.stats["by_type"] = {}
            self.paused = True
        elif cmd == "set_source":
            kind = msg.get("kind", "file")
            kwargs = {k: v for k, v in msg.items() if k not in ("cmd", "kind")}
            await self._switch_source(kind, **kwargs)
        elif cmd == "set_decoder":
            # 切换解码模式: custom / pyais / compare
            mode = msg.get("mode", "custom")
            if mode in ("custom", "pyais", "compare"):
                self._decoder_mode = mode
                # 切换解码器类型
                if mode == "pyais":
                    self._unified_decoder = UnifiedDecoder(DecoderType.PYAIS)
                elif mode == "compare":
                    self._unified_decoder = UnifiedDecoder(DecoderType.BOTH)
                else:
                    self._unified_decoder = UnifiedDecoder(DecoderType.CUSTOM)
                log.info(f"Decoder mode changed to: {mode}")


# 单例
service = AISService()
