"""消息 20 — Data Link Management Message。

无位置信息,仅解析 mmsi。预留以避免丢弃解析机会。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 72:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 20:
        return -1

    mmsi = get_bits(bits, 8, 30)

    out.mmsi = mmsi
    out.msg_type = 20
    return 0
