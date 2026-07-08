# ITU-R M.1371-4 字段笔记

## 6-bit ASCII 映射 (附件 8 表 44,libais 工程实现)

AIS 载荷每个 ASCII 字符只使用低 6 位,有效值 0-63。

```
if ascii in 0x30-0x57 ('0'-'W'):  value = ascii - 0x30
elif ascii in 0x60-0x77 ('`'-'w'):  value = ascii - 0x38
else: 非法
```

| ASCII | 6-bit 值 | ASCII | 6-bit 值 |
|-------|---------|-------|---------|
| `0`-`9` | 0-9 | `@`-`O` | 16-31 |
| `:`-`?` | 10-15 | `P`-`W` | 32-39 |
| `` ` ``-`w` | 40-63 | | |

**易错点**: `P` 映射到 **32**(不是 16);`@` 映射到 16(不是 32)。`X-Z` 非法。

## 消息 1 — A 类位置报告 (168 bits)

```
 0-5    6   message ID (1)
 6-7    2   repeat indicator
 8-37  30   MMSI
38-41   4   navigation status
42-49   8   rate of turn (signed, ±127, value 128 = not available)
50-59  10   SOG (knots, /10)
60-60   1   position accuracy (0=low, 1=high)
61-88  28   longitude (signed, /600000)
89-115 27   latitude (signed, /600000)
116-127 12  COG (deg, /10, 3600 = not available)
128-136 9  true heading (0-359, 511 = not available)
137-142 6  UTC second (0-59, 60 = not available)
143-145 3  special manoeuvre indicator
146-147 2  spare
148-148 1  RAIM flag
149-167 19  communication state
```

经纬度采用 **二进制补码** 表示,负值代表南纬 / 西经。

## 消息 18 — Class B 位置报告 (168 bits)

```
 0-5    6   message ID (18)
 6-7    2   repeat indicator
 8-37  30   MMSI
38-45   8   regional reserved
46-55  10   SOG (/10)
56-56   1   position accuracy
57-84  28   longitude (signed, /600000)
85-111 27   latitude (signed, /600000)
112-123 12  COG (/10)
124-132 9  true heading
133-138 6  UTC second
139-142 4  class B unit flag (CS unit)
143-145 3  class B display flag
146-146 1  class B DSC flag
147-147 1  class B band flag
148-148 1  class B message 22 flag
149-150 2  mode flag
151-153 3  spare
154-167 14  communication state (fixed = 0)
```

## 消息 5 — 静态与航行数据 (424 bits,2 时隙)

```
  0-5    6   message ID (5)
  6-7    2   repeat indicator
  8-37  30   MMSI
 38-39   2   AIS version
 40-69  30   IMO number
 70-111 42   callsign (7 个 6-bit ASCII)
112-231 120  ship name (20 个 6-bit ASCII,@ 填充)
232-239 8   ship type
240-247 8   dimension to bow
248-255 8   dimension to stern
256-263 8   dimension to port
264-271 8   dimension to starboard
272-273 2   EPFD type
274-277 4   UTC month
278-283 6   UTC day
284-288 5   UTC hour
289-294 6   UTC minute
295-295 1   UTC year (high bit)
296-303 8   UTC year (low bits) — 合 9 位
304-311 8   draught (/10, m)
312-431 120  destination (20 个 6-bit ASCII)
432-441 10  DTE flag
```

## BCC 校验

计算 `!` 与 `*` 之间所有字符的逐字节 XOR,与 `*xx` 比较。

```python
def bcc_check(line: str) -> bool:
    star = line.find('*')
    if star < 0 or not line.startswith('!'):
        return False
    payload = line[1:star]
    expected = int(line[star+1:star+3], 16)
    xor = 0
    for ch in payload:
        xor ^= ord(ch)
    return xor == expected
```

## 6-bit 解码示例

输入载荷 `13u?etPv2;0n:d4wP60R0N1TRDp`,填充位 `0`:

- 共 28 字符 × 6 位 = 168 位,与消息 1 一致
- 首 6 位 = `000001`(消息 1)
- 接下来 2 位 = `00`(repeat=0)
- 接下来 30 位 = MMSI

## 在线验证

- https://aggsoft.com/ais-decoder.htm
- https://catb.org/gpsd/AIVDM.html
- pyais (Python 参考实现)
- libais (C++ 参考实现)