"""解码统一入口。

按接口契约 `decode_ais(payload, out) -> int` 实现。

支持消息类型:
- 1, 2, 3: A 类位置报告 (SOTDMA/ITDMA)
- 4: 基站报告
- 5: A 类静态与航行数据
- 18: B 类位置报告
- 19: B 类扩展位置报告
- 20: 数据链路管理消息
- 21: 航标报告
- 24: B 类静态数据

对于位置消息 (1,2,3,4,18,19,21) 解析经纬度、航速、航向等;
对于静态消息 (5,24) 解析船名、呼号等;
其他消息仅提取 MMSI。
"""
from __future__ import annotations

from .ais_ship import AIS_Ship
from .bitstream import get_bits
from .nmea import FragmentBuffer
from .sixbit import payload_to_bitstring

from . import msg1, msg2, msg3, msg4, msg5, msg18, msg19, msg20, msg21, msg24


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

    # A 类位置报告 (1, 2, 3 共用同一布局)
    if msg_id == 1:
        return msg1.parse(bits, out)
    if msg_id == 2:
        return msg2.parse(bits, out)
    if msg_id == 3:
        return msg3.parse(bits, out)

    # 基站报告
    if msg_id == 4:
        return msg4.parse(bits, out)

    # A 类静态与航行数据
    if msg_id == 5:
        return msg5.parse(bits, out)

    # B 类位置报告
    if msg_id == 18:
        return msg18.parse(bits, out)

    # B 类扩展位置报告
    if msg_id == 19:
        return msg19.parse(bits, out)

    # 数据链路管理消息 (仅提取 MMSI)
    if msg_id == 20:
        return msg20.parse(bits, out)

    # 航标报告
    if msg_id == 21:
        return msg21.parse(bits, out)

    # B 类静态数据
    if msg_id == 24:
        return msg24.parse(bits, out)

    # 暂不支持的消息类型
    return -1


__all__ = ["decode_ais", "FragmentBuffer"]