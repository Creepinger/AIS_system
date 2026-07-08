"""消息 21 — Aids-to-Navigation Report (可变长度)。

字段布局参考 ITU-R M.1371-5 §3.3.7.2.7。
注意：消息 21 长度可变，name 字段可能不足 120 bits。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits, get_signed
from .sixbit import bits_to_6bit_ascii


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 272:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 21:
        return -1

    mmsi = get_bits(bits, 8, 30)
    lon_raw = get_signed(bits, 57, 28)
    lat_raw = get_signed(bits, 85, 27)

    # name: 从 bit 163 开始，长度可变 (最多 120 bits = 20 chars)
    # 消息 21 长度至少 272 bits，name 字段可能不完整
    name_start = 163
    name_end = min(len(bits), 283)  # 最多到 bit 282 (20 chars)
    name_bits = bits[name_start:name_end]

    # 补齐到 6 的倍数
    remainder = len(name_bits) % 6
    if remainder:
        name_bits = name_bits + [0] * (6 - remainder)
    shipname = bits_to_6bit_ascii(name_bits, trim=True).strip()

    out.mmsi = mmsi
    out.msg_type = 21
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    if shipname:
        out.shipname = shipname
    return 0
