"""使用 pyais 生成真实测试样本。"""
from pyais.encode import encode_dict

# 消息 1
m1a = encode_dict(dict(type=1, mmsi="477553200", lat=22.316667, lon=114.183333,
                       course=181.0, speed=0.0), radio_channel="B")
m1b = encode_dict(dict(type=1, mmsi="367430230", lat=37.802, lon=-122.341,
                       course=219.3, speed=12.4), radio_channel="B")
# 消息 18
m18a = encode_dict(dict(type=18, mmsi="538090479", lat=40.0, lon=-74.0,
                        course=90.0, speed=8.5), radio_channel="B")
# 消息 5(静态数据,会拆成 2 段)
m5a = encode_dict(dict(type=5, mmsi="477553200", shipname="TEST VESSEL",
                       callsign="VR2TEST", shiptype=70, destination="HONG KONG"),
                  radio_channel="B")

with open("tests/samples/sample_nmea.txt", "w", encoding="utf-8") as f:
    for line in m1a + m1b + m18a + m5a:
        f.write(line + "\n")

print("Wrote", "tests/samples/sample_nmea.txt")
for line in m1a + m1b + m18a + m5a:
    print(line)