"""位流工具。

AIS 解码核心操作:从 0/1 位列表中按 (start, length) 提取值。
支持有符号(2 补码,用于经纬度、转向率)。
"""
from __future__ import annotations


def get_bits(buf: list[int], start: int, length: int) -> int:
    """从位流 `buf` 中提取 [start, start+length) 的位,作为无符号整数返回。

    Args:
        buf: 0/1 列表,长度 ≥ start + length。
        start: 起始位(0-based,高位在前)。
        length: 位宽(1-32)。
    """
    if start < 0 or length <= 0:
        raise ValueError(f"invalid start={start}, length={length}")
    if length > 32:
        raise ValueError(f"length too large: {length}")
    end = start + length
    if end > len(buf):
        raise IndexError(
            f"bit range out of bounds: need {end} bits, buf has {len(buf)}"
        )
    v = 0
    for i in range(start, end):
        v = (v << 1) | (buf[i] & 1)
    return v


def get_signed(buf: list[int], start: int, length: int) -> int:
    """按二进制补码解释。

    AIS 协议中经纬度(28/27 bit)、转向率(8 bit)使用 2 补码。
    """
    raw = get_bits(buf, start, length)
    sign_bit = 1 << (length - 1)
    if raw & sign_bit:
        raw -= 1 << length
    return raw