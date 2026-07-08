"""消息 4 — Base Station Report (168 bits)。

与 msg1 大体相同,但没有 sog/cog/nav_status,含 UTC 时间戳。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits, get_signed


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 168:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 4:
        return -1

    mmsi = get_bits(bits, 8, 30)
    lon_raw = get_signed(bits, 61, 28)
    lat_raw = get_signed(bits, 89, 27)
    utc_sec_raw = get_bits(bits, 137, 6)

    out.mmsi = mmsi
    out.msg_type = 4
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    out.utc_second = -1 if utc_sec_raw >= 60 else utc_sec_raw
    return 0
