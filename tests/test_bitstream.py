"""位提取工具测试。"""
import pytest

from ais.bitstream import get_bits, get_signed
from ais.sixbit import payload_to_bitstring


def test_get_bits_unsigned():
    buf = [1, 0, 1, 1, 0, 0, 1, 0]
    assert get_bits(buf, 0, 8) == 0xB2


def test_get_bits_subrange():
    buf = [1, 0, 1, 1, 0, 0, 1, 0]
    assert get_bits(buf, 2, 4) == 0b1100


def test_get_bits_zero_length():
    with pytest.raises(ValueError):
        get_bits([0, 1], 0, 0)


def test_get_bits_out_of_bounds():
    with pytest.raises(IndexError):
        get_bits([1, 0], 0, 8)


def test_get_signed_positive():
    buf = [0, 1, 1, 1, 1, 1, 1, 1]
    assert get_signed(buf, 0, 8) == 127


def test_get_signed_negative():
    buf = [1, 1, 1, 1, 1, 1, 1, 1]
    assert get_signed(buf, 0, 8) == -1


def test_get_signed_min():
    buf = [1, 0, 0, 0, 0, 0, 0, 0]
    assert get_signed(buf, 0, 8) == -128


def test_msg1_real_mmsi_extraction():
    """用真实样本验证 msg_type + repeat + mmsi 提取。"""
    bits = payload_to_bitstring("177KR<?P008:d9P<i@d74P01P000", 0)
    msg_id = get_bits(bits, 0, 6)
    repeat = get_bits(bits, 6, 2)
    mmsi = get_bits(bits, 8, 30)
    assert msg_id == 1
    assert repeat == 0
    assert mmsi == 477553200