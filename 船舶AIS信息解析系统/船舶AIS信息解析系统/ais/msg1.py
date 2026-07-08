"""消息 1 — A 类位置报告 (168 bits)。

字段偏移见 docs/protocol_notes.md。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits, get_signed
from .sixbit import payload_to_bitstring


# 字段 (start_bit, length, signed, scale)
def parse(bits: list[int], out: AIS_Ship) -> int:
    """从位流解析消息 1,填充 out。

    Returns:
        0 成功;-1 位流长度不足或字段非法。
    """
    if len(bits) < 168:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 1:
        return -1

    mmsi = get_bits(bits, 8, 30)
    nav_status = get_bits(bits, 38, 4)
    rot_raw = get_signed(bits, 42, 8)
    sog_raw = get_bits(bits, 50, 10)
    pos_accuracy = get_bits(bits, 60, 1)
    lon_raw = get_signed(bits, 61, 28)
    lat_raw = get_signed(bits, 89, 27)
    cog_raw = get_bits(bits, 116, 12)
    heading_raw = get_bits(bits, 128, 9)
    utc_sec_raw = get_bits(bits, 137, 6)

    out.mmsi = mmsi
    out.msg_type = 1
    out.utc_second = -1 if utc_sec_raw >= 60 else utc_sec_raw

    # 特殊值约定:
    #  SOG = 1023 (10-bit 全 1) → 未知,记为 0
    #  COG = 3600 (12-bit 全 1) → 未知,记为 0
    #  Heading = 511 → 未知
    #  ROT = 128 → 未知 (再 +1 偏移在协议外有;此处保持 raw)
    out.sog = 0.0 if sog_raw >= 1023 else sog_raw / 10.0
    out.cog = 0 if cog_raw >= 3600 else int(cog_raw / 10.0)
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    # pos_accuracy / nav_status 暂不入字段,需要可加;注释保留供扩展:
    # out.nav_status = nav_status
    # out.pos_accuracy = pos_accuracy
    return 0