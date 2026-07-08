"""测试脚本：验证自研解析器和 pyais 库对比。

用法:
    python tests/test_dual_decoder.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ais.unified_decoder import UnifiedDecoder, DecoderType
from ais.bcc import bcc_check


def test_dual_decode(sample_file: Path | None = None) -> int:
    """测试双解码器。

    Args:
        sample_file: NMEA 样本文件路径

    Returns:
        0 全部通过, 1 有失败
    """
    if sample_file is None:
        sample_file = PROJECT_ROOT / "AIS one hour 202506.txt"

    if not sample_file.exists():
        print(f"[ERROR] 样本文件不存在: {sample_file}")
        return 1

    # 创建对比模式解码器
    decoder = UnifiedDecoder(DecoderType.BOTH)

    lines = [ln.strip() for ln in sample_file.read_text(encoding="utf-8").splitlines()
             if ln.strip()]

    print(f"正在测试 {len(lines)} 条 NMEA 语句...")
    print("=" * 60)

    success_count = 0
    fail_count = 0
    compare_count = 0

    for line in lines:
        if not bcc_check(line):
            continue

        result = decoder.decode_and_compare(line)

        if not result.success:
            fail_count += 1
            continue

        success_count += 1

        # 打印有对比数据的记录
        if result.custom_ship and result.pyais_dict:
            compare_count += 1
            print(f"\n[MMSI: {result.mmsi}] [类型: {result.msg_type}]")
            print(f"  自研  | 纬度: {result.custom_ship.latitude:>12.5f}  经度: {result.custom_ship.longitude:>13.5f}")
            print(f"  pyais | 纬度: {result.pyais_dict.get('lat', 0):>12.5f}  经度: {result.pyais_dict.get('lon', 0):>13.5f}")
            if result.msg_type in (1, 2, 3, 18, 19):
                print(f"  误差  | Δlat: {result.lat_error:.6f}  Δlon: {result.lon_error:.6f}")

        # 只显示前 20 条对比结果
        if compare_count >= 20:
            print("\n... (后续结果省略)")
            break

    print("\n" + "=" * 60)
    print(f"测试完成:")
    print(f"  总处理: {len(lines)} 条")
    print(f"  解码成功: {success_count} 条")
    print(f"  失败: {fail_count} 条")
    print(f"  对比数据: {compare_count} 条")
    print(f"\n解码器统计: {decoder.get_stats()}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(test_dual_decode(p))
