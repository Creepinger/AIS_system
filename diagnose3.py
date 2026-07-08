"""诊断 parse_line 被拒的 740 行是什么情况。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ais.bcc import bcc_check
from ais.nmea import parse_line, NmeaSentence
from ais.sixbit import payload_to_bitstring, SixBitError

FILE = Path(__file__).parent / "AIS one hour 202506.txt"

bcc_ok = parse_ok = 0
rejected = []
sixbit_issues = 0

with open(FILE, encoding="utf-8", errors="replace") as f:
    for i, raw in enumerate(f, 1):
        line = raw.rstrip("\r\n")
        if not line or not line.startswith("!"):
            continue
        if not bcc_check(line):
            continue
        bcc_ok += 1
        sent = parse_line(line)
        if sent is None:
            rejected.append((i, line))
        else:
            parse_ok += 1
            try:
                bits = payload_to_bitstring(sent.payload, 0)
            except SixBitError as e:
                sixbit_issues += 1

print(f"BCC 通过的 ! 行 : {bcc_ok}")
print(f"parse_line 通过 : {parse_ok}  ({parse_ok*100//bcc_ok if bcc_ok else 0}%)")
print(f"parse_line 拒绝 : {bcc_ok - parse_ok}  ({(bcc_ok-parse_ok)*100//bcc_ok if bcc_ok else 0}%)")
print(f"其中 sixbit 非法 : {sixbit_issues}")
print()
print("=== 被 parse_line 拒绝的前 20 行 ===")
for lineno, line in rejected[:20]:
    print(f"  行{lineno}: {line[:80]}")
