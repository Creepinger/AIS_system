"""消息 18 解析测试(用 pyais 编码的真实样本)。"""
from ais.ais_ship import AIS_Ship
from ais.msg18 import parse as parse_msg18
from ais.sixbit import payload_to_bitstring

# MMSI=538090479, lat=40.0, lon=-74.0, course=90, speed=8.5
SAMPLE_18 = "B81:Ksh0EFcD505f=P0p@0000000"
EXPECTED_MMSI = 538090479


def test_payload_length_168():
    bits = payload_to_bitstring(SAMPLE_18, 0)
    assert len(bits) == 168


def test_msg18_mmsi():
    bits = payload_to_bitstring(SAMPLE_18, 0)
    s = AIS_Ship()
    assert parse_msg18(bits, s) == 0
    assert s.msg_type == 18
    assert s.mmsi == EXPECTED_MMSI


def test_msg18_lat_lon():
    bits = payload_to_bitstring(SAMPLE_18, 0)
    s = AIS_Ship()
    parse_msg18(bits, s)
    assert abs(s.latitude - 40.0) < 0.01
    assert abs(s.longitude - (-74.0)) < 0.01


def test_msg18_wrong_id():
    bits = payload_to_bitstring(SAMPLE_18, 0)
    bits[0:6] = [0, 0, 0, 0, 0, 1]   # msg id = 1
    s = AIS_Ship()
    assert parse_msg18(bits, s) == -1


def test_msg18_too_short():
    s = AIS_Ship()
    assert parse_msg18([0] * 50, s) == -1