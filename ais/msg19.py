"""消息 19 — Extended Class B Position Report (312 bits)。"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits, get_signed
from .sixbit import bits_to_6bit_ascii


def parse(bits: list[int], out: AIS_Ship) -> int:
    if len(bits) < 312:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 19:
        return -1

    mmsi = get_bits(bits, 8, 30)
    sog_raw = get_bits(bits, 46, 10)
    lon_raw = get_signed(bits, 57, 28)
    lat_raw = get_signed(bits, 85, 27)
    cog_raw = get_bits(bits, 112, 12)
    heading_raw = get_bits(bits, 124, 9)
    utc_sec_raw = get_bits(bits, 133, 6)
    name_bits = bits[143:263]
    shipname = bits_to_6bit_ascii(name_bits, trim=True).strip()

    out.mmsi = mmsi
    out.msg_type = 19
    out.utc_second = -1 if utc_sec_raw >= 60 else utc_sec_raw
    out.sog = 0.0 if sog_raw >= 1023 else sog_raw / 10.0
    out.cog = 0 if cog_raw >= 3600 else int(cog_raw / 10.0)
    out.longitude = lon_raw / 600000.0
    out.latitude = lat_raw / 600000.0
    if shipname:
        out.shipname = shipname
    return 0
