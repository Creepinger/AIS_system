"""AIS_Ship 数据类简单测试。"""
from ais.ais_ship import AIS_Ship


def test_default_values():
    s = AIS_Ship()
    assert s.mmsi == 0
    assert s.latitude == 0.0
    assert s.longitude == 0.0
    assert s.sog == 0.0
    assert s.cog == 0
    assert s.shipname == ""
    assert s.msg_type == 0
    assert s.utc_second == -1


def test_to_row_columns():
    s = AIS_Ship(mmsi=123456789, latitude=31.5, longitude=121.7,
                 sog=12.3, cog=89, shipname="TEST", msg_type=1, utc_second=42)
    row = s.to_row()
    assert row[0] == 123456789
    assert row[1] == "31.50000"
    assert row[2] == "121.70000"
    assert row[3] == "12.3"
    assert row[4] == 89
    assert row[5] == "TEST"
    assert row[6] == 42
    assert row[7] == 1


def test_to_row_unknown_utc():
    s = AIS_Ship(msg_type=5, utc_second=-1)
    row = s.to_row()
    assert row[6] == "-"


def test_to_dict_keys():
    s = AIS_Ship()
    d = s.to_dict()
    assert "mmsi" in d and "latitude" in d and "shipname" in d