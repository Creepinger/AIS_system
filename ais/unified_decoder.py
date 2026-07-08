"""统一解码接口。

提供解码器抽象层，支持在「自研解析器」和「pyais库」之间切换，
用于对比两种解码方式的结果，或根据需求选择不同实现。

使用方式:
    from ais.unified_decoder import UnifiedDecoder, DecoderType

    # 使用自研解析器
    decoder = UnifiedDecoder(DecoderType.CUSTOM)
    decoder.decode_nmea(line, ship)

    # 使用 pyais 库
    decoder = UnifiedDecoder(DecoderType.PYAIS)
    decoder.decode_nmea(line, ship)

    # 同时使用两种方式，对比结果
    decoder = UnifiedDecoder(DecoderType.BOTH)
    result = decoder.decode_and_compare(line)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

from .ais_ship import AIS_Ship
from .nmea import NmeaSentence, parse_line, FragmentBuffer
from .bcc import bcc_check

# 自研解析器
from . import decoder as custom_decoder

# pyais 解析器
from .pyais_decoder import PyAISDecoder


class DecoderType(Enum):
    """解码器类型枚举。"""
    CUSTOM = "custom"       # 自研解析器
    PYAIS = "pyais"        # pyais 库
    BOTH = "both"           # 同时使用两种方式


@dataclass
class DecodeResult:
    """解码结果容器。"""
    success: bool = False
    msg_type: int = 0
    mmsi: int = 0

    # 自研解析器结果
    custom_ship: Optional[AIS_Ship] = None

    # pyais 解析器结果
    pyais_dict: Optional[dict[str, Any]] = None

    # 误差分析（位置消息类型）
    lat_error: float = 0.0
    lon_error: float = 0.0
    sog_error: float = 0.0
    cog_error: float = 0.0

    # 错误信息
    error_msg: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典用于前端展示。"""
        # 计算是否需要显示误差
        has_errors = self.msg_type in (1, 2, 3, 4, 18, 19, 21)
        both_have_data = self.custom_ship and self.pyais_dict

        result = {
            "success": self.success,
            "msg_type": self.msg_type,
            "mmsi": self.mmsi,
            "error": self.error_msg,
        }

        if self.custom_ship:
            result["custom"] = self.custom_ship.to_dict()

        if self.pyais_dict:
            result["pyais"] = self.pyais_dict

        # 有任意一个结果且是位置消息类型时，显示误差
        if has_errors and both_have_data:
            result["errors"] = {
                "lat": round(self.lat_error, 6),
                "lon": round(self.lon_error, 6),
                "sog": round(self.sog_error, 2),
                "cog": round(self.cog_error, 2),
            }

        return result


class UnifiedDecoder:
    """统一解码器。

    支持三种模式:
    - CUSTOM: 仅使用自研解析器
    - PYAIS: 仅使用 pyais 库
    - BOTH: 同时使用两种方式，可对比结果
    """

    def __init__(self, decoder_type: DecoderType = DecoderType.CUSTOM) -> None:
        self.decoder_type = decoder_type
        self.custom_frag = FragmentBuffer()
        self.pyais_decoder = PyAISDecoder()
        self.stats: dict[str, int] = {
            "total": 0,
            "bcc_fail": 0,
            "custom_success": 0,
            "custom_fail": 0,
            "pyais_success": 0,
            "pyais_fail": 0,
        }

    def decode_nmea(self, nmea_line: str, out: AIS_Ship) -> int:
        """解码一条 NMEA 语句。

        Args:
            nmea_line: 完整的 NMEA 语句
            out: 待填充的 AIS_Ship

        Returns:
            0 成功, -1 失败
        """
        self.stats["total"] += 1

        # BCC 校验
        if not bcc_check(nmea_line):
            self.stats["bcc_fail"] += 1
            return -1

        if self.decoder_type == DecoderType.CUSTOM:
            return self._decode_custom(nmea_line, out)
        elif self.decoder_type == DecoderType.PYAIS:
            return self._decode_pyais(nmea_line, out)
        else:
            # BOTH 模式：优先用自定义，失败则用 pyais
            rc = self._decode_custom(nmea_line, out)
            if rc == 0:
                return 0
            return self._decode_pyais(nmea_line, out)

    def _decode_custom(self, nmea_line: str, out: AIS_Ship) -> int:
        """使用自研解析器解码。"""
        sent = parse_line(nmea_line)
        if sent is None:
            self.stats["custom_fail"] += 1
            return -1

        payload = self.custom_frag.feed(sent)
        if payload is None:
            self.stats["custom_fail"] += 1
            return -1

        rc = custom_decoder.decode_ais(payload, out)
        if rc == 0:
            self.stats["custom_success"] += 1
        else:
            self.stats["custom_fail"] += 1
        return rc

    def _decode_pyais(self, nmea_line: str, out: AIS_Ship) -> int:
        """使用 pyais 库解码。"""
        rc = self.pyais_decoder.decode_nmea(nmea_line, out)
        if rc == 0:
            self.stats["pyais_success"] += 1
        else:
            self.stats["pyais_fail"] += 1
        return rc

    def decode_and_compare(self, nmea_line: str) -> DecodeResult:
        """解码并对比两种方式的结果。

        适用于调试和对拍场景。

        Args:
            nmea_line: 完整的 NMEA 语句

        Returns:
            DecodeResult 对象，包含两种方式的结果和误差分析
        """
        result = DecodeResult()

        # BCC 校验
        if not bcc_check(nmea_line):
            result.error_msg = "BCC checksum failed"
            return result

        # 解析 NMEA
        sent = parse_line(nmea_line)
        if sent is None:
            result.error_msg = "NMEA parse failed"
            return result

        # 自研解析器
        custom_ship = AIS_Ship()
        payload = self.custom_frag.feed(sent)
        if payload:
            custom_rc = custom_decoder.decode_ais(payload, custom_ship)
            if custom_rc == 0:
                result.custom_ship = custom_ship
                result.msg_type = custom_ship.msg_type
                result.mmsi = custom_ship.mmsi

        # pyais 解析器
        try:
            from pyais import decode as pyais_decode
            from pyais.exceptions import AISBaseException
            pyais_msg = pyais_decode(nmea_line)
            result.pyais_dict = pyais_msg.asdict()
            # 如果还没有 msg_type/mmsi，用 pyais 的结果填充
            if result.msg_type == 0:
                result.msg_type = result.pyais_dict.get("msg_type", 0)
            if result.mmsi == 0:
                result.mmsi = result.pyais_dict.get("mmsi", 0)
        except (AISBaseException, ValueError) as e:
            if not result.error_msg:
                result.error_msg = f"pyais error: {e}"

        # 误差分析（仅对位置消息）
        # 只要有任意一个解码器成功就算成功
        if result.custom_ship or result.pyais_dict:
            result.success = True
            if result.custom_ship and result.pyais_dict:
                self._compute_errors(result)

        return result

    def _compute_errors(self, result: DecodeResult) -> None:
        """计算两种解码方式的误差。"""
        if result.msg_type not in (1, 2, 3, 4, 18, 19, 21):
            return

        custom = result.custom_ship
        pyais = result.pyais_dict

        if custom is None or pyais is None:
            return

        # 纬度误差
        ref_lat = pyais.get("lat", 0)
        if ref_lat is not None and -90 <= ref_lat <= 90:
            result.lat_error = abs(custom.latitude - ref_lat)

        # 经度误差
        ref_lon = pyais.get("lon", 0)
        if ref_lon is not None and -180 <= ref_lon <= 180:
            result.lon_error = abs(custom.longitude - ref_lon)

        # 航速误差
        ref_sog = pyais.get("speed", 0)
        if ref_sog is not None:
            result.sog_error = abs(custom.sog - ref_sog)

        # 航向误差（考虑环形）
        ref_cog = pyais.get("course", 0)
        if ref_cog is not None:
            diff = abs(custom.cog - ref_cog)
            result.cog_error = min(diff, 360 - diff)

    def reset(self) -> None:
        """重置解码器状态。"""
        self.custom_frag = FragmentBuffer()
        self.pyais_decoder.reset()
        self.stats = {
            "total": 0,
            "bcc_fail": 0,
            "custom_success": 0,
            "custom_fail": 0,
            "pyais_success": 0,
            "pyais_fail": 0,
        }

    def get_stats(self) -> dict[str, Any]:
        """获取解码统计信息。"""
        return {
            **self.stats,
            "decoder_type": self.decoder_type.value,
        }


# 模块级便捷函数
def decode_with_both(nmea_line: str) -> Optional[DecodeResult]:
    """便捷函数：同时使用两种方式解码并对比。

    Args:
        nmea_line: 完整的 NMEA 语句

    Returns:
        DecodeResult 或 None
    """
    decoder = UnifiedDecoder(DecoderType.BOTH)
    return decoder.decode_and_compare(nmea_line)


__all__ = [
    "UnifiedDecoder",
    "DecoderType",
    "DecodeResult",
    "decode_with_both",
]
