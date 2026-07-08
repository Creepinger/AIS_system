"""6-bit ASCII 解码 / 编码。

权威定义来自 `bcl/aisparser`(libais 工程实现),与 ITU-R M.1371-4 表 44 一致:

    if (ascii < 0x60):
        value = (ascii - 0x30) & 0x3F       # 0x30-0x57 ('0'-'W')
    else:
        value = (ascii - 0x38) & 0x3F       # 0x60-0x77 ('`'-'w')

合法字符:
  '0'..'9'   → 0-9
  ':'..'?'   → 10-15
  '@'..'O'   → 16-31   ('@'=0x40-0x30=16, 'A'=0x41-0x30=17, ..., 'O'=0x4F-0x30=31)
  'P'..'W'   → 32-39   ('P'=0x50-0x30=32, ..., 'W'=0x57-0x30=39)
  '`'..'w'   → 40-63   ('`'=0x60-0x38=40, 'a'=0x61-0x38=41, ..., 'w'=0x77-0x38=63)
  其他字符 → 非法

注:gpsd 文档给出的另一种"@" + "@_" 的描述是历史遗留,与工程实践不符;
    libais / pyais 等主流实现均采用本表。

提供:
- `ascii6_to_int(c)`:单个字符 → 6-bit 整数
- `payload_to_bitstring(payload, pad_bits)`:整段载荷 → 0/1 位列表
- `bits_to_6bit_ascii(bits, trim)`:位流 → ASCII 字符串
"""
from __future__ import annotations


class SixBitError(ValueError):
    """6-bit 字符非法。"""


def ascii6_to_int(c: str) -> int:
    """单字符 → 6-bit 整数(0-63)。"""
    if len(c) != 1:
        raise SixBitError(f"expected single char, got {c!r}")
    code = ord(c)
    # 合法区间:0x30-0x57 或 0x60-0x77
    if 0x30 <= code <= 0x57:
        v = code - 0x30
    elif 0x60 <= code <= 0x77:
        v = code - 0x38
    else:
        raise SixBitError(
            f"invalid 6-bit ASCII char: {c!r} (ord=0x{code:02X}); "
            f"valid range 0x30-0x57 ('0'-'W') or 0x60-0x77 ('`'-'w')"
        )
    return v & 0x3F


def int_to_ascii6(v: int) -> str:
    """6-bit 值 → ASCII 字符。"""
    if not 0 <= v <= 63:
        raise SixBitError(f"6-bit value out of range: {v}")
    if v < 40:
        # v < 40 时映射回 0x30-0x57
        return chr(v + 0x30)
    # v >= 40 映射到 0x60-0x77
    return chr(v + 0x38)


# 向后兼容别名
ascii6_to_char = int_to_ascii6


def payload_to_bitstring(payload: str, pad_bits: int = 0) -> list[int]:
    """将 6-bit ASCII 载荷转为 0/1 位列表(MSB first)。

    Args:
        payload: 载荷字符串。
        pad_bits: 末尾填充位数。

    Returns:
        长度为 `len(payload) * 6 + pad_bits` 的 list[int]。

    Raises:
        SixBitError: 包含非法字符。
    """
    bits: list[int] = []
    for c in payload:
        v = ascii6_to_int(c)
        for i in range(5, -1, -1):
            bits.append((v >> i) & 1)
    bits.extend([0] * pad_bits)
    return bits


def bits_to_6bit_ascii(bits: list[int], trim: bool = True) -> str:
    """位流(长度 6 的倍数) → ASCII 字符串。

    Args:
        bits: 0/1 列表。
        trim: True 时按 ITU 标准去除第一个 `@`(6-bit 0)及之后字符。
    """
    if len(bits) % 6 != 0:
        raise ValueError(f"bit length must be multiple of 6, got {len(bits)}")
    out: list[str] = []
    for i in range(0, len(bits), 6):
        v = 0
        for j in range(6):
            v = (v << 1) | (bits[i + j] & 1)
        out.append(int_to_ascii6(v))
    s = "".join(out)
    if trim:
        at = s.find("@")
        if at >= 0:
            s = s[:at]
    return s