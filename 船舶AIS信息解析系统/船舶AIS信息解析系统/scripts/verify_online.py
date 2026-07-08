"""解码对拍脚本。

用法:
    python scripts/verify_online.py tests/samples/sample_nmea.txt
    python scripts/verify_online.py                       # 默认样本

从样本中提取消息,使用 pyais(权威开源实现)解码作为对照。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyais import decode as pyais_decode

from ais.bcc import bcc_check
from ais.nmea import parse_line
from ais.decoder import FragmentBuffer, decode_ais
from ais.ais_ship import AIS_Ship


def verify(path: Path) -> int:
    failures = 0
    total = 0
    buf = FragmentBuffer()
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip()]

    for line in lines:
        if not bcc_check(line):
            print(f"[BCC FAIL] {line[:60]}...")
            continue
        sent = parse_line(line)
        if sent is None:
            continue
        payload = buf.feed(sent)
        if payload is None:
            continue
        total += 1
        ship = AIS_Ship()
        if decode_ais(payload, ship) != 0:
            continue

        # 用 pyais 作为对照
        try:
            ref = pyais_decode(line)
            d = ref.asdict()
        except Exception as e:
            print(f"[PYAIS ERR] {e} ({line[:60]})")
            continue

        print(f"\n--- type={ship.msg_type} mmsi={ship.mmsi} ---")
        print(f"  我们的 : lat={ship.latitude:.5f}  lon={ship.longitude:.5f}  "
              f"sog={ship.sog:.1f}  cog={ship.cog}")
        ref_lat = d.get("lat", 91)
        ref_lon = d.get("lon", 181)
        ref_sog = d.get("speed", 0)
        ref_cog = d.get("course", 0)
        print(f"  pyais  : lat={ref_lat:.5f}  lon={ref_lon:.5f}  "
              f"speed={ref_sog:.1f}  course={ref_cog}")

        if ship.msg_type in (1, 18):
            err_lat = abs(ship.latitude - ref_lat) if abs(ref_lat) <= 90 else 0
            err_lon = abs(ship.longitude - ref_lon) if abs(ref_lon) <= 180 else 0
            err_sog = abs(ship.sog - ref_sog)
            err_cog = min(abs(ship.cog - ref_cog), 360 - abs(ship.cog - ref_cog))
            ok = (err_lat < 0.001 and err_lon < 0.001 and
                  err_sog < 0.5 and err_cog <= 2)
            tag = "PASS" if ok else "FAIL"
            print(f"  差异   : Δlat={err_lat:.5f}  Δlon={err_lon:.5f}  "
                  f"Δsog={err_sog:.2f}  Δcog={err_cog}  → {tag}")
            if not ok:
                failures += 1

    print(f"\n=== 共 {total} 条解码,失败 {failures} ===")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    default = PROJECT_ROOT / "tests" / "samples" / "sample_nmea.txt"
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    sys.exit(verify(p))