"""深度诊断:BCC 失败原因 + 各消息类型解码结果。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ais.bcc import bcc_check, compute_bcc
from ais.nmea import parse_line
from ais.sixbit import payload_to_bitstring, SixBitError
from ais.bitstream import get_bits
from ais.decoder import decode_ais
from ais.ais_ship import AIS_Ship

FILE = Path(__file__).parent / "AIS one hour 202506.txt"

total = bcc_ok = bcc_fail = parse_ok = decoded = 0
sixbit_errors = 0
by_talker = {}
by_msg_id = {}
decoded_by_msg = {}
bcc_fail_samples = []

with open(FILE, encoding="utf-8", errors="replace") as f:
    for i, raw in enumerate(f, 1):
        total += 1
        line = raw.rstrip("\r\n")
        if not line:
            continue

        ok = bcc_check(line)
        if ok:
            bcc_ok += 1
            sent = parse_line(line)
            if sent:
                parse_ok += 1
                t = sent.talker
                by_talker[t] = by_talker.get(t, 0) + 1
                bits = payload_to_bitstring(sent.payload, 0)
                msg_id = get_bits(bits, 0, 6)
                by_msg_id[msg_id] = by_msg_id.get(msg_id, 0) + 1
                ship = AIS_Ship()
                rc = decode_ais(sent.payload, ship)
                if rc == 0:
                    decoded += 1
                    decoded_by_msg[msg_id] = decoded_by_msg.get(msg_id, 0) + 1
        else:
            bcc_fail += 1
            if len(bcc_fail_samples) < 10:
                star = line.find("*")
                if star >= 0:
                    tail = line[star + 1 : star + 3]
                    calc = compute_bcc(line)
                    bcc_fail_samples.append((i, line[:60], tail, f"0x{calc:02X}"))

print("=== BCC 统计 ===")
print(f"总行数      : {total}")
print(f"BCC 通过    : {bcc_ok}  ({bcc_ok*100//total}%)")
print(f"BCC 失败    : {bcc_fail}  ({bcc_fail*100//total}%)")
print()
print("=== BCC 失败样本 (行号, 行前60字符, 文件*XX, 计算值) ===")
for lineno, snippet, file_xor, calc in bcc_fail_samples:
    print(f"  行{lineno}: '{snippet}' | file={file_xor} calc={calc}")

print()
print("=== 通过 BCC 的行解析 ===")
print(f"parse_line OK: {parse_ok}  ({parse_ok*100//bcc_ok if bcc_ok else 0}%)")
print(f"解码成功     : {decoded}  ({decoded*100//parse_ok if parse_ok else 0}%)")
print()
print(f"按 talker : {dict(sorted(by_talker.items()))}")
print()
print(f"按 msg_id (全部): {dict(sorted(by_msg_id.items()))}")
print()
print(f"按 msg_id (仅成功解码): {dict(sorted(decoded_by_msg.items()))}")
