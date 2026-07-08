"""消息 21 — Aids-to-Navigation Report (272 bits)。

字段布局参考 ITU-R M.1371-5 §3.3.7.2.7。
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
    name_bits = bits[163:263]
    shipname = bits_to_6bit_ascii(name_bits, trim=True).strip()

    out.mmsi = mmsi
    out.msg_type = 21
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    if shipname:
        out.shipname = shipname
    return 0
