"""pyais 库解码封装。

使用第三方库 pyais (https://github.com/M0r13n/pyais) 进行 AIS 消息解码。
pyais 实现了 ITU-R M.1371 标准中定义的所有消息类型 (1-27)。

本模块将 pyais 的解码结果统一转换为 AIS_Ship 数据结构。
"""
from __future__ import annotations

from typing import Optional, Any

from pyais import decode as pyais_decode
from pyais.exceptions import AISBaseException, InvalidNMEAMessageException

from .ais_ship import AIS_Ship
from .nmea import FragmentBuffer


class PyAISDecoder:
    """pyais 解码器封装类。"""

    def __init__(self) -> None:
        self.frag = FragmentBuffer()
        self.decoded_count = 0
        self.error_count = 0

    def decode_nmea(self, nmea_line: str, out: AIS_Ship) -> int:
        """解码一条 NMEA 语句。

        Args:
            nmea_line: 完整的 NMEA 语句 (含 !AIVDM 前缀和 *xx 校验)
            out: 待填充的 AIS_Ship

        Returns:
            0 成功, -1 失败
        """
        try:
            # pyais 可以直接解码 NMEA 语句，自动处理多帧拼接
            msg = pyais_decode(nmea_line)

            # 转换为 AIS_Ship
            self._msg_to_ship(msg, out)
            self.decoded_count += 1
            return 0

        except (AISBaseException, InvalidNMEAMessageException, ValueError) as e:
            self.error_count += 1
            return -1

    def decode_payload(self, payload: str, out: AIS_Ship) -> int:
        """解码已拼接的 payload (需外部处理多帧拼接)。

        Args:
            payload: 6-bit ASCII 载荷字符串
            out: 待填充的 AIS_Ship

        Returns:
            0 成功, -1 失败
        """
        try:
            # 将 payload 转换为虚拟的 NMEA 行
            # pyais 的 decode 函数支持多种输入格式
            msg = pyais_decode(payload)
            self._msg_to_ship(msg, out)
            self.decoded_count += 1
            return 0

        except (AISBaseException, InvalidNMEAMessageException, ValueError) as e:
            self.error_count += 1
            return -1

    def _msg_to_ship(self, msg: Any, out: AIS_Ship) -> None:
        """将 pyais 的解码结果转换为 AIS_Ship。"""
        # 获取基础属性
        out.mmsi = getattr(msg, "mmsi", 0) or 0
        out.msg_type = getattr(msg, "msg_type", 0) or 0

        # 位置信息
        lat = getattr(msg, "lat", None)
        lon = getattr(msg, "lon", None)
        out.latitude = lat if lat is not None else 0.0
        out.longitude = lon if lon is not None else 0.0

        # 速度和航向 (pyais 用 speed/course, AIS_Ship 用 sog/cog)
        speed = getattr(msg, "speed", None)
        course = getattr(msg, "course", None)
        out.sog = speed if speed is not None else 0.0
        out.cog = int(course) if course is not None else 0

        # 时间戳
        utc_second = getattr(msg, "timestamp", None)
        if utc_second is not None and 0 <= utc_second < 60:
            out.utc_second = int(utc_second)
        else:
            out.utc_second = -1

        # 船名 (可能在静态消息中)
        shipname = getattr(msg, "shipname", None)
        if shipname:
            out.shipname = shipname.strip()

        # 备选船名 (Part B)
        if not out.shipname:
            name_to_20 = getattr(msg, "name_to_20", None)
            if name_to_20:
                out.shipname = name_to_20.strip()

    def reset(self) -> None:
        """重置解码器状态。"""
        self.frag = FragmentBuffer()
        self.decoded_count = 0
        self.error_count = 0

    @property
    def stats(self) -> dict[str, int]:
        """返回解码统计信息。"""
        return {
            "decoded": self.decoded_count,
            "errors": self.error_count,
        }


# 模块级便捷函数
def decode_with_pyais(nmea_line: str) -> Optional[dict[str, Any]]:
    """便捷函数：直接解码一条 NMEA 语句并返回字典。

    Args:
        nmea_line: 完整的 NMEA 语句

    Returns:
        解码结果的字典，失败返回 None
    """
    try:
        msg = pyais_decode(nmea_line)
        return msg.asdict()
    except (AISBaseException, InvalidNMEAMessageException, ValueError):
        return None


def get_supported_msg_types() -> list[int]:
    """返回 pyais 支持的消息类型列表。

    基于 ITU-R M.1371 标准，主要类型包括:
    - 1,2,3: A 类位置报告
    - 4: 基站报告
    - 5: A 类静态与航行数据
    - 18: B 类位置报告
    - 19: B 类扩展位置报告
    - 20: 数据链路管理
    - 21: 航标报告
    - 24: B 类静态数据
    """
    return [1, 2, 3, 4, 5, 18, 19, 20, 21, 24, 27]
