# 接口契约 (Interface Contract)

> 本文件由组长(Core)在 Day 1 下午锁定,组员 A 与组员 B 必须基于此实现。
> **一旦发布,字段名/类型/方法签名不再修改**,新增字段只能追加。

## 1. 数据结构 `AIS_Ship`

定义位置: `ais/ais_ship.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| `mmsi` | `int` | 船舶识别码,30 bit 无符号 |
| `latitude` | `float` | 纬度(度),**南纬为负数** |
| `longitude` | `float` | 经度(度),**西经为负数** |
| `sog` | `float` | 对地航速(节,0-102.2) |
| `cog` | `int` | 对地航向(度,0-359) |
| `shipname` | `str` | 船名,消息 5 解析后填入(≤20 字符) |
| `msg_type` | `int` | 消息类型(1, 5, 18, 24 等) |
| `utc_second` | `int` | UTC 秒(0-59),消息 1/18 才有 |

## 2. 解码入口 `decode_ais`

```python
def decode_ais(payload: str, out: AIS_Ship) -> int:
    """
    输入:
        payload: 组员 A 拼接好的完整 6-bit ASCII 字符串
                (不含 !AIVDM 头与 *xx 校验)
        out:     调用方提供的 AIS_Ship 实例,函数会原地填充

    返回:
        0  成功
       -1  payload 为空 / 消息类型未知 / 字段长度不合法
    """
```

调用约定:

- 仅依赖 `payload` 字段,**不**涉及多帧拼接(由 `FragmentBuffer` 处理)
- 不做 NMEA 拆包与 BCC(由 `ais/nmea.py` 处理)
- 线程安全:无副作用,纯函数

## 3. 多帧缓存器 `FragmentBuffer`

```python
buf = FragmentBuffer()

# 组员 A 每读到一条 NMEA 语句:
sent = parse_line(line)            # 返回 NmeaSentence 或 None
payload = buf.feed(sent)           # 返回完整 payload 字符串或 None
if payload is not None:
    decode_ais(payload, ship)
```

- 内部以 `(channel, sequence_id)` 维护 dict,收到第 1 句时缓存,到 `total` 句拼接完成返回
- 超时(默认 5 秒)未收齐自动丢弃,避免僵尸 sequence

## 4. UI 刷新信号

```python
# ui/controller.py
class Controller(QObject):
    ship_received = Signal(object)   # 参数: AIS_Ship 实例
    stats_changed = Signal(dict)      # 参数: {rx, ok, bad, decoded}
    error = Signal(str)
```

组员 B 的 `ShipTable` 与 `GridCanvas` 必须订阅 `ship_received` 槽。
**禁止**在解码模块直接引用 PySide6 类(保持分层)。

> **v1.1 备注**:PySide6 桌面 GUI 已废弃,改用 Web 前端(见 §5)。原 Qt
> 模块保留在 `ui/` 目录作为离线参考实现。

## 5. Web 前端通道(v1.1 新增)

### 5.1 HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 返回 `web/static/index.html`(Leaflet 主页) |
| GET | `/healthz` | 健康检查 + 当前数据源/船舶数/在线客户端数 |
| POST | `/api/load` | 切换数据源。表单字段:`kind`(file/serial/net)、`path`、可选 `upload` 文件 |
| GET | `/static/*` | 前端静态资源 |

### 5.2 WebSocket `/ws`

#### 服务端 → 客户端(每 200ms 一次批)

```json
{
  "type": "batch",
  "ts": 1720000000.0,
  "source": "文件: tests/samples/sample_nmea.txt",
  "paused": false,
  "stats": {
    "rx": 12, "bcc_pass": 11, "bcc_fail": 1, "decoded": 10,
    "by_type": {"1": 3, "5": 1, "18": 1},
    "ship_count": 4, "started_at": 1720000000.0, "uptime_sec": 5
  },
  "ships": [
    {"mmsi": 477553200, "latitude": 22.31667, "longitude": 114.18333,
     "sog": 0.0, "cog": 181, "shipname": "", "msg_type": 1, "utc_second": 42,
     "timestamp": 1720000000.1}
  ]
}
```

#### 客户端 → 服务端命令

```json
{"cmd": "pause"}
{"cmd": "resume"}
{"cmd": "clear"}
{"cmd": "set_source", "kind": "file",    "path": "D:/data/x.txt"}
{"cmd": "set_source", "kind": "serial",  "serial_port": "COM3", "baudrate": 38400}
{"cmd": "set_source", "kind": "net",     "host": "127.0.0.1", "port": 5000}
```

### 5.3 Web 模块清单

| 模块 | 职责 |
|------|------|
| [web/app.py](../web/app.py) | FastAPI 路由 + lifespan 启停 AISService |
| [web/ws.py](../web/ws.py) | ConnectionManager 多客户端广播 + 断线清理 |
| [web/decoder_service.py](../web/decoder_service.py) | 协议解析 + 增量船舶表 + 统计 + 200ms 批量推送 |
| [web/link_async.py](../web/link_async.py) | 文件/串口/网口的纯 asyncio 数据源 |
| [web/static/index.html](../web/static/index.html) | 单页 HTML,Leaflet 地图 + 侧边表格 |
| [web/static/js/ws_client.js](../web/static/js/ws_client.js) | WebSocket 客户端(自动重连) |
| [web/static/js/map.js](../web/static/js/map.js) | Leaflet 初始化、marker、cog 旋转、popup |
| [web/static/js/stats.js](../web/static/js/stats.js) | 状态面板 + 船舶列表 + 控制按钮 |

## 5. 版本与变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0  | Day 1 | 首次发布 |
| 1.1  | Day 4 | 增加 WebSocket 通道(`/ws`)与 HTTP 上传/换源(`/api/load`) |