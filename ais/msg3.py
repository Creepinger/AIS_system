"""消息 3 — Position Report with ITDMA (168 bits,与 msg1 同布局)。"""
from .msg1 import parse as parse_msg1


def parse(bits: list[int], out):
    rc = parse_msg1(bits, out)
    if rc == 0 and getattr(out, "msg_type", 0) == 1:
        out.msg_type = 3
    return rc
