"""NMEA 0183 语句拆包。

提供:
- `NmeaSentence`:拆包后的中间结构
- `parse_line(line)`:解析单行 NMEA
- `FragmentBuffer`:多帧拼接器(消息 5 等长消息使用)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .bcc import bcc_check


@dataclass
class NmeaSentence:
    """一条已拆包的 NMEA 0183 语句。"""

    talker: str            # 如 "AIVDM"
    total: int             # 总句数
    index: int             # 当前句号(1-based,1..total)
    seq_id: int            # 序列 ID(可为 0)
    channel: str           # "A" / "B" / "C" / "D"
    payload: str           # 6-bit ASCII 载荷(不含填充与校验)
    pad_bits: int          # 末尾填充位数
    raw_line: str          # 原始行

    @property
    def key(self) -> tuple[str, int]:
        """多帧缓存的 key:同一序列的多个语句共享此 key。"""
        return (self.channel, self.seq_id)


def parse_line(line: str) -> Optional[NmeaSentence]:
    """解析单行 NMEA 语句(已通过 BCC 校验)。

    期望格式:`!AIVDM,total,index,seq,channel,payload,pad*xx`
    """
    if not line or not line.startswith("!"):
        return None
    star = line.find("*")
    if star < 0:
        return None
    body = line[1:star]                       # `AIVDM,total,index,seq,channel,payload,pad`
    fields = body.split(",")
    # 至少需要 5 段: talker,total,index,seq,channel;
    # payload 与 pad 字段允许缺失(默认空串/0)
    if len(fields) < 5:
        return None
    talker = fields[0]
    # 接受任何 talker 只要以 VDM/VDO 结尾(NMEA 0183 AIS 句)。
    # 允许常见前缀: AI(标准船→站)/ AB(基站聚合)/ AN/ AP/ AS 等。
    if not (talker.endswith("VDM") or talker.endswith("VDO")):
        return None
    try:
        total = int(fields[1]) if fields[1] else 1
        index = int(fields[2]) if fields[2] else 1
        seq_id = int(fields[3]) if fields[3] else 0
        channel = fields[4] if len(fields) > 4 else ""
        payload = fields[5] if len(fields) > 5 else ""
        pad_bits = int(fields[6]) if len(fields) > 6 and fields[6] else 0
    except ValueError:
        return None
    # 单条 / 多条 index 都用 1..total 编码;若与 total 不一致也接受
    return NmeaSentence(
        talker=talker,
        total=total,
        index=index,
        seq_id=seq_id,
        channel=channel,
        payload=payload,
        pad_bits=pad_bits,
        raw_line=line,
    )


def parse_and_check(line: str) -> Optional[NmeaSentence]:
    """先 BCC 校验,再拆包。失败返回 None。"""
    if not bcc_check(line):
        return None
    return parse_line(line)


class FragmentBuffer:
    """多帧 NMEA 拼接器。

    使用 `(channel, seq_id)` 作为 key:
      - 收到第 1 句时缓存
      - 后续句按 index 追加
      - 全部到齐返回完整 payload,否则继续等
      - 缺帧超过 timeout_sec 自动丢弃,避免僵尸序列
    """

    def __init__(self, timeout_sec: float = 5.0) -> None:
        self.timeout_sec = timeout_sec
        # key -> {"expected": total, "received": set[int], "parts": dict[int, NmeaSentence], "ts": float}
        self._buf: dict[tuple[str, int], dict] = {}

    def feed(self, sent: NmeaSentence) -> Optional[str]:
        """送入一条已拆包的语句。返回完整 payload 字符串,或不完整时返回 None。"""
        if sent.total == 1:
            # 单条即可返回
            self._cleanup()
            return sent.payload

        # 多条:按 index 1..total 缓存拼接
        idx = sent.index
        key = sent.key
        slot = self._buf.get(key)
        if slot is None:
            slot = {
                "expected": sent.total,
                "received": set(),
                "parts": {},
                "ts": time.monotonic(),
            }
            self._buf[key] = slot
        # 重复或越界直接忽略
        if idx in slot["received"] or idx < 1 or idx > slot["expected"]:
            return None
        slot["received"].add(idx)
        slot["parts"][idx] = sent
        slot["ts"] = time.monotonic()

        if len(slot["received"]) == slot["expected"]:
            payload = "".join(slot["parts"][i].payload for i in range(1, slot["expected"] + 1))
            del self._buf[key]
            return payload
        return None

    def _cleanup(self) -> None:
        """清理超时序列。"""
        now = time.monotonic()
        dead = [k for k, v in self._buf.items() if now - v["ts"] > self.timeout_sec]
        for k in dead:
            del self._buf[k]