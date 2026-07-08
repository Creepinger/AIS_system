"""BCC 异或校验。

NMEA 0183 语句:!AIVDM,1,1,,A,13u?...,0*25
计算 `!` 与 `*` 之间所有字符的逐字节 XOR,与 `*` 后两位十六进制比较。
"""
from __future__ import annotations


def bcc_check(line: str) -> bool:
    """校验 NMEA 语句的 BCC 字段。

    Args:
        line: 完整 NMEA 语句(含 `!` 与 `*xx` 校验和)。

    Returns:
        True 表示校验通过。
    """
    if not line or not line.startswith("!"):
        return False
    star = line.find("*")
    if star < 0 or len(line) < star + 3:
        return False

    body = line[1:star]
    tail = line[star + 1 : star + 3]
    if len(tail) != 2:
        return False

    try:
        expected = int(tail, 16)
    except ValueError:
        return False

    xor = 0
    for ch in body:
        xor ^= ord(ch)
    return xor == expected


def compute_bcc(line: str) -> int:
    """计算 `!` 与 `*` 之间所有字符的 XOR 值(不含 *xx)。"""
    star = line.find("*")
    if star < 0:
        raise ValueError("missing '*' in line")
    xor = 0
    for ch in line[1:star]:
        xor ^= ord(ch)
    return xor