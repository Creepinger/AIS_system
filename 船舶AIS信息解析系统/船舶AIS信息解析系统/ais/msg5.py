"""消息 5 — 静态与航行数据(2 时隙,共 424 bits)。

跨 2 条 NMEA 语句,载荷在 `FragmentBuffer` 拼接后传入本模块。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits
from .sixbit import bits_to_6bit_ascii


def parse(bits: list[int], out: AIS_Ship) -> int:
    """解析消息 5,只填充 mmsi / shipname / msg_type(用于与 msg1 关联)。

    Returns:
        0 成功;-1 位流长度不足或消息 ID 错误。
    """
    if len(bits) < 424:
        return -1

    msg_id = get_bits(bits, 0, 6)
    if msg_id != 5:
        return -1

    mmsi = get_bits(bits, 8, 30)

    # callsign: 70-111 共 42 位 = 7 个 6-bit ASCII
    callsign_bits = bits[70:112]
    callsign = bits_to_6bit_ascii(callsign_bits, trim=True)

    # ship name: 112-231 共 120 位 = 20 个 6-bit ASCII,@ 填充
    name_bits = bits[112:232]
    shipname = bits_to_6bit_ascii(name_bits, trim=True)

    out.mmsi = mmsi
    out.msg_type = 5
    # 优先使用解出的船名;若为空但 callsign 不为空则用 callsign
    out.shipname = shipname.strip() or callsign.strip()
    # 消息 5 不含 sog/cog/lat/lon;保持不变
    return 0