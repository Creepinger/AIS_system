"""消息 2 — Position Report with SOTDMA (168 bits,含 sog/cog)。"""
from .msg1 import parse as parse_msg1


def parse(bits: list[int], out):
    rc = parse_msg1(bits, out)
    if rc == 0 and getattr(out, "msg_type", 0) == 1:
        out.msg_type = 2
    return rc
