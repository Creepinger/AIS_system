"""UI 控制器:IO → decoder → UI 的信号中心。

- 维护统计信息
- 持有 FragmentBuffer
- 把 AIS_Ship 发到 ship_received 信号
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, Slot

from ais.bcc import bcc_check
from ais.decoder import FragmentBuffer, decode_ais
from ais.ais_ship import AIS_Ship
from ais.nmea import parse_line


@dataclass
class Stats:
    rx: int = 0            # 收包总数(无论 BCC)
    bcc_pass: int = 0
    bcc_fail: int = 0
    decoded: int = 0
    by_type: dict = field(default_factory=dict)  # {1: n, 5: n, 18: n}


class Controller(QObject):
    ship_received = Signal(object)  # AIS_Ship
    stats_changed = Signal(object)  # Stats
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.stats = Stats()
        self.frag = FragmentBuffer()
        self.paused = False

    @Slot(str)
    def on_line(self, line: str) -> None:
        if self.paused:
            return
        self.stats.rx += 1
        if not bcc_check(line):
            self.stats.bcc_fail += 1
            self._emit_stats()
            return
        self.stats.bcc_pass += 1
        sent = parse_line(line)
        if sent is None:
            return
        payload = self.frag.feed(sent)
        if payload is None:
            return
        ship = AIS_Ship()
        rc = decode_ais(payload, ship)
        if rc == 0:
            self.stats.decoded += 1
            self.stats.by_type[ship.msg_type] = (
                self.stats.by_type.get(ship.msg_type, 0) + 1
            )
            self.ship_received.emit(ship)
        self._emit_stats()

    def _emit_stats(self) -> None:
        self.stats_changed.emit(self.stats)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def reset(self) -> None:
        self.stats = Stats()
        self.frag = FragmentBuffer()
        self._emit_stats()