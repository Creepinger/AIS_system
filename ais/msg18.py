"""消息 18 — Class B 位置报告 (168 bits)。

字段偏移见 docs/protocol_notes.md(注意 sog/cog 起始位与 msg1 不同)。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits, get_signed


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 168:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 18:
        return -1

    mmsi = get_bits(bits, 8, 30)
    sog_raw = get_bits(bits, 46, 10)
    lon_raw = get_signed(bits, 57, 28)
    lat_raw = get_signed(bits, 85, 27)
    cog_raw = get_bits(bits, 112, 12)
    heading_raw = get_bits(bits, 124, 9)
    utc_sec_raw = get_bits(bits, 133, 6)

    out.mmsi = mmsi
    out.msg_type = 18
    out.utc_second = -1 if utc_sec_raw >= 60 else utc_sec_raw
    out.sog = 0.0 if sog_raw >= 1023 else sog_raw / 10.0
    out.cog = 0 if cog_raw >= 3600 else int(cog_raw / 10.0)
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    # class B 标志(暂不写入 shipname 字段;若需可扩展 AIS_Ship)
    return 0