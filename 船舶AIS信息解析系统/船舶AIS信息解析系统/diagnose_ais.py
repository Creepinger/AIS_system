"""诊断真实数据文件的解析情况。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ais.bcc import bcc_check
from ais.nmea import parse_line
from ais.sixbit import payload_to_bitstring
from ais.bitstream import get_bits

FILE = Path(__file__).parent / "AIS one hour 202506.txt"

total = 0
bcc_ok = 0
parse_ok = 0
decoded = 0
by_talker = {}
by_msg_id = {}
no_star = 0

with open(FILE, encoding="utf-8", errors="replace") as f:
    for raw in f:
        total += 1
        line = raw.strip()
        if not line:
            continue
        if "*" not in line:
            no_star += 1
            continue
        if bcc_check(line):
            bcc_ok += 1
            sent = parse_line(line)
            if sent:
                parse_ok += 1
                t = sent.talker
                by_talker[t] = by_talker.get(t, 0) + 1
                bits = payload_to_bitstring(sent.payload, 0)
                if len(bits) >= 6:
                    msg_id = get_bits(bits, 0, 6)
                    by_msg_id[msg_id] = by_msg_id.get(msg_id, 0) + 1
                from ais.decoder import decode_ais
                from ais.ais_ship import AIS_Ship
                ship = AIS_Ship()
                rc = decode_ais(sent.payload, ship)
                if rc == 0:
                    decoded += 1

print(f"总行数       : {total}")
print(f"含 * (BCC)   : {total - no_star}")
print(f"BCC 通过     : {bcc_ok}")
print(f"parse_line OK: {parse_ok}")
print(f"解码成功     : {decoded}")
print()
print("按 talker:", sorted(by_talker.items()))
print()
print("按 msg_id :", sorted(by_msg_id.items()))
