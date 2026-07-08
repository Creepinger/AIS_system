# 报告章节大纲

> 组长负责的章节用 **[Core]** 标注;组员 A 用 **[Driver]**;组员 B 用 **[UI]**;共同章节用 **[All]**。

## 一、引言 [All]

1.1 项目背景
1.2 智能化导航实验平台简介
1.3 AIS 系统工作原理概述 [Core 统稿]

## 二、需求分析 [All]

2.1 功能需求
2.2 性能需求
2.3 数据接口

## 三、相关技术与协议 [Core 统稿]

3.1 NMEA 0183 协议简介 **[Driver]**
3.2 ITU-R M.1371-4 建议书 **[Core]**
3.3 6-bit ASCII 编码原理 **[Core]**
3.4 PySide6 框架简介 **[UI]**

## 四、系统设计 **[Core 统稿]**

4.1 整体架构
4.2 程序解析流程图 **[Core]**
4.3 模块划分与接口契约 **[Core]**
4.4 数据存储设计 **[Core]**

## 五、关键算法实现

5.1 BCC 校验算法 **[Driver]**
5.2 6-bit ASCII 转二进制原理 **[Core]**
5.3 消息 1 解析 **[Core]**
5.4 消息 18 解析 **[Core]**
5.5 消息 5 多帧拼接与解析 **[Core]**
5.6 串口/网口通信实现 **[Driver]**
5.7 经纬度方格图绘制算法 **[UI]**
5.8 GUI 事件驱动与信号槽 **[UI]**

## 六、系统测试 **[Core 统稿]**

6.1 单元测试
6.2 在线工具对比 (aggsoft / pyais)
6.3 真实数据回放测试

## 七、运行结果与展示 **[UI 统稿]**

7.1 主界面截图
7.2 方格图截图
7.3 数据库截图

## 八、遇到的困难及解决办法 [All 各自]

8.1 协议解析中的难点 **[Core]**
8.2 串口/网口通信难点 **[Driver]**
8.3 界面与可视化难点 **[UI]**

## 九、收获与体会 [All 各自]

## 十、参考文献

---

## 附录 A — 关键算法(组长负责)

### A.1 6-bit ASCII 解码

参见 [`ais/sixbit.py`](../ais/sixbit.py) 与 [`tests/test_sixbit.py`](../tests/test_sixbit.py)。

```python
def ascii6_to_int(c: str) -> int:
    """单字符 → 6-bit 整数(0-63)。

    字符表来源:libais 工程实现(bcl/aisparser)。
    合法区段:ASCII 0x30-0x57 ('0'-'W') 与 0x60-0x77 ('`'-'w')
    """
    code = ord(c)
    if 0x30 <= code <= 0x57:
        return code - 0x30
    if 0x60 <= code <= 0x77:
        return code - 0x38
    raise SixBitError(...)
```

### A.2 消息 1 字段提取

参见 [`ais/msg1.py`](../ais/msg1.py) 与 [`tests/test_msg1.py`](../tests/test_msg1.py)。

字段偏移见 [`docs/protocol_notes.md`](protocol_notes.md)。经纬度采用二进制补码,负值代表南纬/西经。

### A.3 解码主流程

参见 [`ais/decoder.py`](../ais/decoder.py)。

```python
def decode_ais(payload: str, out: AIS_Ship) -> int:
    bits = payload_to_bitstring(payload, 0)
    msg_id = get_bits(bits, 0, 6)
    if msg_id == 1:  return msg1.parse(bits, out)
    if msg_id == 5:  return msg5.parse(bits, out)
    if msg_id == 18: return msg18.parse(bits, out)
    return -1
```

## 附录 B — 测试覆盖

| 模块 | 测试文件 | 用例数 |
|------|---------|--------|
| 6-bit ASCII | `tests/test_sixbit.py` | 16 |
| 位提取 | `tests/test_bitstream.py` | 8 |
| BCC 校验 | `tests/test_bcc.py` | 9 |
| NMEA 拆包 | `tests/test_nmea.py` | 6 |
| 消息 1 | `tests/test_msg1.py` | 8 |
| 消息 18 | `tests/test_msg18.py` | 5 |
| 消息 5 | `tests/test_msg5.py` | 5 |
| AIS_Ship | `tests/test_ais_ship.py` | 4 |
| **合计** | | **61** |

```
============================= 61 passed in 0.07s ==============================
```

## 附录 C — 与 pyais 库对拍结果

```
--- type=1 mmsi=477553200 ---
  我们的 : lat=22.31667  lon=114.18333  sog=0.0  cog=181
  pyais  : lat=22.31667  lon=114.18333  speed=0.0  course=181.0
  差异   : Δlat=0.00000  Δlon=0.00000  Δsog=0.00  Δcog=0.0  → PASS

--- type=1 mmsi=367430230 ---
  我们的 : lat=37.80200  lon=-122.34100  sog=12.4  cog=219
  pyais  : lat=37.80200  lon=-122.34100  speed=12.4  course=219.3
  差异   : Δlat=0.00000  Δlon=0.00000  Δsog=0.00  Δcog=0.3  → PASS

--- type=18 mmsi=538090479 ---
  我们的 : lat=40.00000  lon=-74.00000  sog=8.5  cog=90
  pyais  : lat=40.00000  lon=-74.00000  speed=8.5  course=90.0
  差异   : Δlat=0.00000  Δlon=0.00000  Δsog=0.00  Δcog=0.0  → PASS
```

4/4 通过。