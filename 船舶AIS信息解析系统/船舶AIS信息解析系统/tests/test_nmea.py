"""NMEA 拆包与多帧拼接测试。"""
from ais.nmea import parse_line, FragmentBuffer


def test_parse_single_sentence():
    s = parse_line("!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10")
    assert s is not None
    assert s.talker == "AIVDO"
    assert s.total == 1
    assert s.index == 1
    assert s.channel == "B"
    assert s.payload == "177KR<?P008:d9P<i@d74P01P000"
    assert s.pad_bits == 0


def test_parse_rejects_non_ais():
    assert parse_line("$GPGGA,...") is None
    assert parse_line("") is None
    assert parse_line("!XYZDM,1,1,,A,X,0*00") is None  # XYZDM ends-with VDM but talker is 3-chars: rejected


def test_fragment_single_part():
    fb = FragmentBuffer()
    s = parse_line("!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10")
    assert fb.feed(s) == "177KR<?P008:d9P<i@d74P01P000"


def test_fragment_multi_part_message5():
    p1 = parse_line("!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C")
    p2 = parse_line("!AIVDO,2,2,0,B,00000000000,2*25")
    assert p1 is not None and p2 is not None

    fb = FragmentBuffer()
    assert fb.feed(p1) is None
    full = fb.feed(p2)
    assert full is not None
    assert full == p1.payload + p2.payload


def test_fragment_dedup_repeat():
    p1 = parse_line("!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C")
    fb = FragmentBuffer()
    assert fb.feed(p1) is None
    assert fb.feed(p1) is None  # 重复忽略


def test_fragment_index_out_of_range_ignored():
    p1 = parse_line("!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C")
    p3_fake = parse_line("!AIVDO,2,9,0,B,FOO,0*00")  # 非法 index=9
    fb = FragmentBuffer()
    assert fb.feed(p1) is None
    assert fb.feed(p3_fake) is None  # 忽略