"""BCC 校验测试(用真实样本)。"""
from ais.bcc import bcc_check, compute_bcc


def test_real_sample_pass():
    # pyais 编码的样本, BCC 实测一致
    assert bcc_check("!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10")


def test_another_real_sample():
    assert bcc_check("!AIVDO,1,1,,B,15NJ:EgP1tG?ur@E`FL8T@01P000,0*77")


def test_msg18_sample():
    assert bcc_check("!AIVDO,1,1,,B,B81:Ksh0EFcD505f=P0p@0000000,0*19")


def test_msg5_part1():
    assert bcc_check(
        "!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C"
    )


def test_msg5_part2():
    assert bcc_check("!AIVDO,2,2,0,B,00000000000,2*25")


def test_tampered_fails():
    assert not bcc_check("!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*11")


def test_missing_star():
    assert not bcc_check("!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0")


def test_no_bang():
    assert not bcc_check("AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10")


def test_compute_bcc_matches():
    line = "!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10"
    assert compute_bcc(line) == 0x10