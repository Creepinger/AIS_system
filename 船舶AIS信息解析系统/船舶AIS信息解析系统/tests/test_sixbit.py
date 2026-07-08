"""6-bit ASCII 解码测试。

权威字符表来自 libais (bcl/aisparser) 工程实现:
  ascii in 0x30-0x57  → value = ascii - 0x30
  ascii in 0x60-0x77  → value = ascii - 0x38
"""
import pytest

from ais.sixbit import (
    ascii6_to_int,
    int_to_ascii6,
    payload_to_bitstring,
    bits_to_6bit_ascii,
    SixBitError,
)


def test_digit_range():
    for i in range(10):
        assert ascii6_to_int(chr(0x30 + i)) == i


def test_colon_question_range():
    # : 0x3A → 10, ..., ? 0x3F → 15
    for i in range(6):
        assert ascii6_to_int(chr(0x3A + i)) == 10 + i


def test_at_sign_is_16():
    assert ascii6_to_int("@") == 16


def test_a_to_o_range():
    # A 0x41 → 17, ..., O 0x4F → 31
    for i in range(15):
        assert ascii6_to_int(chr(0x41 + i)) == 17 + i


def test_p_to_w_range():
    # P 0x50 → 32, ..., W 0x57 → 39
    for i in range(8):
        assert ascii6_to_int(chr(0x50 + i)) == 32 + i


def test_backtick_to_w():
    # ` 0x60 → 40, a 0x61 → 41, ..., w 0x77 → 63
    assert ascii6_to_int("`") == 40
    assert ascii6_to_int("a") == 41
    for i in range(23):
        assert ascii6_to_int(chr(0x61 + i)) == 41 + i


def test_x_y_z_invalid():
    # X 0x58, Y 0x59, Z 0x5A 在 (0x57, 0x60) 范围内,本表视为非法
    with pytest.raises(SixBitError):
        ascii6_to_int("X")
    with pytest.raises(SixBitError):
        ascii6_to_int("Z")


def test_invalid_chars():
    # 0x28-0x2F, 0x58-0x5F, 0x78-0x7F 均为非法
    illegal = [
        "(", ")", "*", "+", "-", ".", "/",       # 0x28-0x2F
        "X", "Y", "Z",                            # 0x58-0x5A
        "\\", "]", "^", "_",                      # 0x5C-0x5F
        "{", "|", "}", "~",                       # 0x7B-0x7E
        "\x7f",                                   # DEL
        " ", "!", "\"", "$", "%", "&", "'",       # 0x20-0x27
    ]
    for c in illegal:
        with pytest.raises(SixBitError):
            ascii6_to_int(c)


def test_round_trip_all_legal():
    for v in range(64):
        c = int_to_ascii6(v)
        assert ascii6_to_int(c) == v, f"round-trip mismatch v={v}, c={c!r}"


def test_payload_to_bitstring_known():
    # '0' = 0 → 000000; 'A' = 17 → 010001
    bits = payload_to_bitstring("0A", 0)
    assert bits == [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1]


def test_payload_length_168_for_msg1():
    # 消息 1 载荷必须正好 168 位(28 字符 × 6 = 168)
    bits = payload_to_bitstring("177KR<?P008:d9P<i@d74P01P000", 0)
    assert len(bits) == 28 * 6 == 168


def test_payload_with_pad():
    bits = payload_to_bitstring("177KR<?P008:d9P<i@d74P01P000", 2)
    assert len(bits) == 168 + 2


def test_bits_to_ascii_round_trip():
    s = "13u?etPv2"
    bits = payload_to_bitstring(s, 0)
    out = bits_to_6bit_ascii(bits, trim=False)
    assert out == s


def test_bits_to_ascii_trims_at_sign():
    # '@' = 0 (6-bit),被 trim
    bits = payload_to_bitstring("P@@@@", 0)
    assert bits_to_6bit_ascii(bits, trim=True) == "P"


def test_bits_to_ascii_no_trim_keeps_at():
    bits = payload_to_bitstring("P@@@@", 0)
    assert bits_to_6bit_ascii(bits, trim=False) == "P@@@@"


def test_bits_length_must_be_multiple_of_6():
    with pytest.raises(ValueError):
        bits_to_6bit_ascii([1, 0, 1, 0, 1])