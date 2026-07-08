"""AIS 协议解析引擎(组长职责)。

支持自研解析器 (decode_ais) 和 pyais 库 (pyais_decoder) 两种解码方式。
可通过 unified_decoder.UnifiedDecoder 统一使用，或直接调用具体函数。
"""
from .ais_ship import AIS_Ship
from .bcc import bcc_check
from .bitstream import get_bits, get_signed
from .decoder import decode_ais, FragmentBuffer
from .nmea import parse_line, NmeaSentence
from .sixbit import ascii6_to_int, payload_to_bitstring
from .pyais_decoder import PyAISDecoder, decode_with_pyais, get_supported_msg_types
from .unified_decoder import (
    UnifiedDecoder,
    DecoderType,
    DecodeResult,
    decode_with_both,
)

__all__ = [
    # 基础类
    "AIS_Ship",
    # BCC 校验
    "bcc_check",
    # 位流工具
    "get_bits",
    "get_signed",
    # NMEA 解析
    "parse_line",
    "NmeaSentence",
    # 6-bit 工具
    "ascii6_to_int",
    "payload_to_bitstring",
    # 自研解码器
    "decode_ais",
    "FragmentBuffer",
    # pyais 解码器
    "PyAISDecoder",
    "decode_with_pyais",
    "get_supported_msg_types",
    # 统一解码接口
    "UnifiedDecoder",
    "DecoderType",
    "DecodeResult",
    "decode_with_both",
]