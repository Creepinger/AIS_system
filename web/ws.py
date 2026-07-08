"""WebSocket 连接管理器。

职责:接收客户端连接、把广播消息分发出去;断线自动清理。
线程安全由 FastAPI 单事件循环保证。
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("WS connected; total=%d", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        log.info("WS disconnected; total=%d", len(self._clients))

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, payload: dict) -> None:
        """向所有连接广播;发送失败的连接会被剔除。"""
        if not self._clients:
            return
        dead: list[WebSocket] = []
        # 拷贝一份避免迭代时修改
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception as e:
                log.warning("WS send failed: %s", e)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# 单例,全应用共享
manager = ConnectionManager()
