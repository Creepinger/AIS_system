"""计算样本真实 BCC,用于校准 sample_nmea.txt 与测试。"""
LINES = [
    ("A", "15MwkT1P37G?fl0EJbR0OwT0@MS"),
    ("B", "15MwkT1P37G?fl0EJbR0OwT0@MS"),
    ("A", "13u?etPv2;0n:d4wP60R0N1TRDp"),
    ("B", "13u?etPv2;0n:d4wP60R0N1TRDp"),
]

print("# Single-sentence samples")
for ch, payload in LINES:
    body = f"AIVDM,1,1,,{ch},{payload},0"
    x = 0
    for c in body:
        x ^= ord(c)
    print(f"!{body}*{x:02X}")

# Multi-part: 计划书的 5-1 / 5-2
multi1 = "AIVDM,2,1,1,A,55Mwj`P00001L17SW:Ov?`050t0R0`<T42>0Fi=20<tT43C,0"
multi2 = "AIVDM,2,2,1,A,00000000000,2"
for body in (multi1, multi2):
    x = 0
    for c in body:
        x ^= ord(c)
    print(f"!{body}*{x:02X}")