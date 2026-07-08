"""消息 24 — Class B CS Static and Voyage Related Data (可变长度)。

Part A: shipname (120 bits @ bit 112)
Part B: 船型 + 厂商 ID + 呼号 + 船舶尺度
参考 ITU-R M.1371-5 §3.3.7.2.10
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits
from .sixbit import bits_to_6bit_ascii


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 160:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 24:
        return -1

    part_no = get_bits(bits, 38, 2)
    mmsi = get_bits(bits, 8, 30)

    out.mmsi = mmsi
    out.msg_type = 24

    if part_no == 0:
        # Part A: shipname (120 bits @ 112..232)
        if len(bits) < 232:
            return -1
        name_bits = bits[112:232]
        # 补齐到 6 的倍数
        remainder = len(name_bits) % 6
        if remainder:
            name_bits = name_bits + [0] * (6 - remainder)
        shipname = bits_to_6bit_ascii(name_bits, trim=True).strip()
        if shipname:
            out.shipname = shipname
        return 0

    if part_no == 1:
        # Part B: ship_type(8bits@132) + vendor_id(18bits@140) + callsign(42bits@158) + dim(30bits@200)
        # name_to_20 (20 chars @ 132): 120 bits
        if len(bits) < 252:
            return -1
        name_bits = bits[132:252]
        # 补齐到 6 的倍数
        remainder = len(name_bits) % 6
        if remainder:
            name_bits = name_bits + [0] * (6 - remainder)
        shipname = bits_to_6bit_ascii(name_bits, trim=True).strip()
        if shipname:
            out.shipname = shipname
        return 0

    # part_no == 2/3:扩展量,不填字段,记录 mmsi 以便关联
    return 0
