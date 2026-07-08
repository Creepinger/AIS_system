"""AIS 船舶信息数据类。

对齐接口契约 v1.0:字段名 / 类型不再变更。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import time
from typing import Any


@dataclass
class AIS_Ship:
    """单条船舶的一次解码结果。

    字段语义见 docs/interface_contract.md。
    """

    mmsi: int = 0
    latitude: float = 0.0       # 南纬为负
    longitude: float = 0.0      # 西经为负
    sog: float = 0.0            # 节
    cog: int = 0                # 0-359
    shipname: str = ""          # 消息 5 填入
    msg_type: int = 0           # 1, 5, 18 ...
    utc_second: int = -1        # -1 表示未知
    timestamp: float = field(default_factory=time.time)

    def to_row(self) -> list[Any]:
        """UI 表格行。"""
        return [
            self.mmsi,
            f"{self.latitude:.5f}",
            f"{self.longitude:.5f}",
            f"{self.sog:.1f}",
            self.cog,
            self.shipname,
            self.utc_second if self.utc_second >= 0 else "-",
            self.msg_type,
        ]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)