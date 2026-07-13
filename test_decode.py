from ais.bcc import bcc_check
from ais.nmea import parse_line, FragmentBuffer
from ais.decoder import decode_ais
from ais.ais_ship import AIS_Ship

lines = [
    '!AIVDO,1,1,,B,177KR<?P008:d9P<i@d74P01P000,0*10',
    '!AIVDO,1,1,,B,15NJ:EgP1tG?ur@E`FL8T@01P000,0*77',
    '!AIVDO,1,1,,B,B81:Ksh0EFcD505f=P0p@0000000,0*19',
    '!AIVDO,2,1,0,B,577KR<000001I;9@E=A@E=B1HE=<Dh0000000000000000000023kQp2kkQh,0*1C',
    '!AIVDO,2,2,0,B,00000000000,2*25',
]

print("=== BCC Check ===")
for line in lines:
    print(f"{bcc_check(line)}: {line[:60]}")

print("\n=== Parse and Decode ===")
frag = FragmentBuffer()
for line in lines:
    sent = parse_line(line)
    if sent:
        payload = frag.feed(sent)
        if payload:
            print(f"\nPayload: {payload[:60]}...")
            ship = AIS_Ship()
            rc = decode_ais(payload, ship)
            print(f"Decode RC: {rc}")
            if rc == 0:
                print(f"MMSI: {ship.mmsi}")
                print(f"Type: {ship.msg_type}")
                print(f"Lat: {ship.latitude}, Lon: {ship.longitude}")
                print(f"SOG: {ship.sog}, COG: {ship.cog}")
        else:
            print(f"Partial: index={sent.index}/{sent.total}")
    else:
        print(f"Parse failed: {line[:40]}")
