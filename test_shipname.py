from ais.bcc import bcc_check
from ais.nmea import parse_line, FragmentBuffer
from ais.sixbit import payload_to_bitstring, bits_to_6bit_ascii
from ais.decoder import decode_ais
from ais.ais_ship import AIS_Ship

line1 = '!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C'
line2 = '!AIVDO,2,2,0,B,00000000000,2*25'

print("=== 解析单条 ===")
sent1 = parse_line(line1)
sent2 = parse_line(line2)

print(f"sent1: talker={sent1.talker}, total={sent1.total}, index={sent1.index}, seq_id={sent1.seq_id}, channel={sent1.channel}, key={sent1.key}")
print(f"sent2: talker={sent2.talker}, total={sent2.total}, index={sent2.index}, seq_id={sent2.seq_id}, channel={sent2.channel}, key={sent2.key}")

print("\n=== 拼接测试 ===")
fb = FragmentBuffer()
result1 = fb.feed(sent1)
print(f"feed(sent1) 返回: {result1}")
result2 = fb.feed(sent2)
print(f"feed(sent2) 返回: {result2}")

if result2:
    print(f"完整载荷: {result2}")
    print(f"载荷长度: {len(result2)}")
    
    # 解码船名
    bits = payload_to_bitstring(result2, sent2.pad_bits)
    name_bits = bits[112:232]
    shipname = bits_to_6bit_ascii(name_bits, trim=True)
    print(f"解码船名: {repr(shipname)}")
    
    # 使用自研解码器
    ship = AIS_Ship()
    rc = decode_ais(result2, ship)
    print(f"\n自研解码器:")
    print(f"MMSI: {ship.mmsi}")
    print(f"船名: {repr(ship.shipname)}")
