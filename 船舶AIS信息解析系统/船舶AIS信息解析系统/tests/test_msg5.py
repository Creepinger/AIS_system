"""消息 5 解析测试(用 pyais 编码的真实样本,跨 2 段)。"""
from ais.ais_ship import AIS_Ship
from ais.msg5 import parse as parse_msg5
from ais.sixbit import payload_to_bitstring, bits_to_6bit_ascii


# 来自 gen_reference_samples.py 的消息 5 跨 2 段
SAMPLE_5_P1 = "577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh"
SAMPLE_5_P2 = "00000000000"
EXPECTED_MMSI = 477553200


def test_payload_full_length_424():
    bits1 = payload_to_bitstring(SAMPLE_5_P1, 0)
    bits2 = payload_to_bitstring(SAMPLE_5_P2, 0)
    full = bits1 + bits2
    assert len(full) >= 424


def test_msg5_mmsi():
    bits1 = payload_to_bitstring(SAMPLE_5_P1, 0)
    bits2 = payload_to_bitstring(SAMPLE_5_P2, 0)
    full = bits1 + bits2
    s = AIS_Ship()
    assert parse_msg5(full, s) == 0
    assert s.msg_type == 5
    assert s.mmsi == EXPECTED_MMSI


def test_msg5_wrong_id():
    bits = payload_to_bitstring(SAMPLE_5_P1, 0) + payload_to_bitstring(SAMPLE_5_P2, 0)
    bits[0:6] = [0, 0, 0, 0, 0, 1]   # msg id = 1
    s = AIS_Ship()
    assert parse_msg5(bits, s) == -1


def test_msg5_too_short():
    s = AIS_Ship()
    assert parse_msg5([0] * 100, s) == -1


def test_bits_to_ascii_msg5():
    """船名字段(112-231 = 120 位 = 20 字符)应能被解码为 ASCII。"""
    bits1 = payload_to_bitstring(SAMPLE_5_P1, 0)
    bits2 = payload_to_bitstring(SAMPLE_5_P2, 0)
    full = bits1 + bits2
    shipname_bits = full[112:232]
    s = bits_to_6bit_ascii(shipname_bits, trim=True)
    # 至少包含几个非填充字符
    assert len(s) > 0