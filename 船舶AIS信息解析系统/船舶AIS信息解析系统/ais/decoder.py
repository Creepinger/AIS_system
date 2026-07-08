"""解码统一入口。

按接口契约 `decode_ais(payload, out) -> int` 实现。

内部根据消息类型分派到 msg1/msg5/msg18。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits
from .nmea import FragmentBuffer
from .sixbit import payload_to_bitstring

from . import msg1, msg5, msg18


def decode_ais(payload: str, out: AIS_Ship) -> int:
    """解析一段已拼接好的完整载荷。

    Args:
        payload: 6-bit ASCII 字符串(不含 !AIVDM 头与 *xx 校验)
        out: 待填充的 AIS_Ship

    Returns:
        0 成功;-1 失败(payload 为空、消息类型未知、长度不足等)。
    """
    if not payload:
        return -1

    bits = payload_to_bitstring(payload, 0)
    if len(bits) < 6:
        return -1

    msg_id = get_bits(bits, 0, 6)

    if msg_id == 1:
        return msg1.parse(bits, out)
    if msg_id == 5:
        return msg5.parse(bits, out)
    if msg_id == 18:
        return msg18.parse(bits, out)

    # 未实现的类型:扩展时在此追加,例如 24, 19 等
    return -1


__all__ = ["decode_ais", "FragmentBuffer"]