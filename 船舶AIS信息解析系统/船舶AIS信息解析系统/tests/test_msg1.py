"""消息 1 解析测试。

样本来自 `tests/gen_reference_samples.py`,经 pyais 编码并 BCC 校验。
"""
from ais.ais_ship import AIS_Ship
from ais.msg1 import parse as parse_msg1
from ais.sixbit import payload_to_bitstring

# MMSI=477553200, lat=22.316667, lon=114.183333, course=181, speed=0
SAMPLE_MMSI_477 = "477553200"
SAMPLE_477 = "177KR<?P008:d9P<i@d74P01P000"

# MMSI=367430230, lat=37.802, lon=-122.341, course=219.3, speed=12.4
SAMPLE_MMSI_367 = "367430230"
SAMPLE_367 = "15NJ:EgP1tG?ur@E`FL8T@01P000"


def test_payload_length_168():
    """消息 1 载荷必须正好 168 位。"""
    bits = payload_to_bitstring(SAMPLE_477, 0)
    assert len(bits) == 168


def test_msg1_mmsi_477():
    bits = payload_to_bitstring(SAMPLE_477, 0)
    s = AIS_Ship()
    assert parse_msg1(bits, s) == 0
    assert s.msg_type == 1
    assert s.mmsi == 477553200


def test_msg1_mmsi_367():
    bits = payload_to_bitstring(SAMPLE_367, 0)
    s = AIS_Ship()
    assert parse_msg1(bits, s) == 0
    assert s.msg_type == 1
    assert s.mmsi == 367430230


def test_msg1_lat_lon_477():
    bits = payload_to_bitstring(SAMPLE_477, 0)
    s = AIS_Ship()
    parse_msg1(bits, s)
    assert abs(s.latitude - 22.316667) < 0.001
    assert abs(s.longitude - 114.183333) < 0.001


def test_msg1_lat_lon_367_negative_lon():
    bits = payload_to_bitstring(SAMPLE_367, 0)
    s = AIS_Ship()
    parse_msg1(bits, s)
    # 西经为负
    assert abs(s.latitude - 37.802) < 0.001
    assert abs(s.longitude - (-122.341)) < 0.001


def test_msg1_sog_cog_367():
    bits = payload_to_bitstring(SAMPLE_367, 0)
    s = AIS_Ship()
    parse_msg1(bits, s)
    assert abs(s.sog - 12.4) < 0.2
    assert abs(s.cog - 219) < 2


def test_msg1_too_short():
    s = AIS_Ship()
    assert parse_msg1([0] * 100, s) == -1


def test_msg1_wrong_id_returns_error():
    # 把前 6 位改成 18(消息 18 ID)
    bits = payload_to_bitstring(SAMPLE_477, 0)
    bits[0:6] = [0, 0, 1, 0, 1, 0]
    s = AIS_Ship()
    assert parse_msg1(bits, s) == -1