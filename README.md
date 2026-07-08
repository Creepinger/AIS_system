# 船舶AIS信息解析系统(基于地图可视化)

基于 FastAPI + Leaflet + OpenStreetMap 的 AIS 报文解析与真实地图可视化系统。
解析引擎严格遵循 ITU-R M.1371-4 建议书。

## 项目组成员分工

| 角色 | 代号 | 核心职责 |
|------|------|---------|
| 组长 | Core | 协议解析引擎(6-bit 解码、消息 1-24 解析、接口契约) |
| 组员 A | Driver | 数据接入(串口/网口/文件)+ BCC 校验 + 多帧拼接(asyncio 版) |
| 组员 B | UI | Web 前端(Leaflet 地图、实时船舶 marker、侧边表格、控制按钮) |

## 功能

- **真实地图可视化** —— Leaflet + OpenStreetMap 瓦片,小三角按 COG 旋转
- **三路数据源** —— 文件回放 / 串口 / TCP 网口(asyncio 异步)
- **双解码器支持** —— 自研解析器 + pyais 库，支持实时切换和结果对比
- **协议解析** —— NMEA 0183 拆包 + BCC 校验 + 多帧拼接 + 消息类型 1-5, 18-21, 24
- **实时推送** —— FastAPI WebSocket 每 200ms 广播船舶快照与统计
- **Web 控制** —— 暂停/继续/清空/换源/上传文件/切换解码器 全部可从浏览器触发

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

```powershell
# 启动 Web 服务
python main.py                       # 默认 http://127.0.0.1:8000

# 自定义端口
python main.py --port 9000

# 启动后,浏览器打开 http://127.0.0.1:8000
# 默认自动加载 tests/samples/sample_nmea.txt
```

### 端口被占用

如果启动时出现 `WinError 10048` 或 `address already in use`,说明 `127.0.0.1:8000` 已经被其他程序占用。

```powershell
# 方案一:换一个端口
python main.py --port 9000

# 方案二:查看占用 8000 的进程
Get-NetTCPConnection -LocalPort 8000 | Select-Object LocalAddress,LocalPort,State,OwningProcess

# 确认进程可以关闭后,结束它
Stop-Process -Id <OwningProcess>
```

打开浏览器后,地图自动居中至首艘船位置,船舶 marker 按 MMSI 实时更新。
侧边栏显示统计与船舶列表,顶部按钮支持暂停/继续/清空/换源/上传新文件。

## 测试

```powershell
# 协议层 61 个单元测试(不依赖 Web)
pytest tests/

# 端到端 WebSocket smoke 测试(需要服务在 8000 端口运行中)
python tests/test_ws_smoke.py

# 与 pyais 库对拍(测试解析精度)
python scripts\verify_online.py
```

```
protocol tests: 61 passed in 0.07s
smoke test: 3 ships, 20 WS frames, rx=5 decoded=4
```

## 目录结构

```
船舶AIS信息解析系统/
├── main.py                       # uvicorn 入口
├── config.py                     # 全局配置(串口/网口/文件/DB/Web)
├── requirements.txt
├── ais/                          # 协议引擎(组长)
│   ├── bcc.py / sixbit.py / bitstream.py
│   ├── nmea.py(FragmentBuffer) / decoder.py(decode_ais)
│   ├── msg1.py / msg2.py / msg3.py / msg4.py
│   ├── msg5.py / msg18.py / msg19.py / msg20.py
│   ├── msg21.py / msg24.py
│   ├── pyais_decoder.py          # pyais 库封装
│   ├── unified_decoder.py         # 统一解码接口
│   └── ais_ship.py
├── link/                         # 数据链路层(原始 PySide6 版本,作为参考保留)
├── web/                          # 新版 Web 前端
│   ├── app.py                    # FastAPI 入口 + 路由
│   ├── ws.py                     # ConnectionManager
│   ├── decoder_service.py        # 协议解析服务(单例，支持双解码器)
│   ├── link_async.py             # asyncio 数据源
│   └── static/
│       ├── index.html            # Leaflet + 侧边表格 + 解码器选择
│       ├── css/style.css
│       └── js/{ws_client,map,stats}.js
├── storage/                      # SQLite/MySQL 持久化
│   ├── schema.sql
│   ├── sqlite_store.py / mysql_store.py
├── tests/                        # 单元测试
│   ├── samples/sample_nmea.txt   # 真实样本(pyais 编码)
│   ├── test_bcc.py / test_sixbit.py / test_bitstream.py
│   ├── test_nmea.py / test_msg1.py / test_msg18.py / test_msg5.py
│   ├── test_ais_ship.py
│   ├── test_dual_decoder.py      # 双解码器对比测试
│   └── test_ws_smoke.py          # WebSocket 端到端
├── scripts/
│   └── verify_online.py          # 与 pyais 对拍
├── docs/
│   ├── interface_contract.md     # 接口契约(含 WebSocket 通道 v1.2)
│   ├── protocol_notes.md         # ITU-R M.1371-4 字段笔记
│   └── report_outline.md
├── data/                         # 运行期数据(自动创建)
│   ├── uploads/                  # 通过浏览器上传的样本
│   ├── raw_log.txt
│   └── parsed_log.txt(可由 storage 层写入)
└── ui/                           # PySide6 旧版(离线参考,可选运行)
    ├── main_window.py / ship_table.py / grid_canvas.py
    └── controller.py
```

## WebSocket 消息格式

### 服务端 → 客户端(每 200ms)

```json
{
  "type": "batch",
  "ts": 1720000000.0,
  "source": "文件: tests/samples/sample_nmea.txt",
  "paused": false,
  "decoder_mode": "custom",
  "stats": {"rx": 12, "bcc_pass": 11, "bcc_fail": 1, "decoded": 10,
            "by_type": {"1":3,"5":1,"18":1}, "ship_count": 4, "uptime_sec": 5},
  "ships": [
    {"mmsi": 477553200, "latitude": 22.31667, "longitude": 114.18333,
     "sog": 0.0, "cog": 181, "shipname": "", "msg_type": 1, "utc_second": 42}
  ],
  "comparison": [
    {
      "msg_type": 1,
      "mmsi": 477553200,
      "custom": {"latitude": 22.31667, "longitude": 114.18333, "sog": 0.0, "cog": 181},
      "pyais": {"lat": 22.31667, "lon": 114.18333, "speed": 0.0, "course": 181},
      "errors": {"lat": 0.000001, "lon": 0.000002, "sog": 0.0, "cog": 0.0}
    }
  ]
}
```

### 客户端 → 服务端命令

```json
{"cmd": "pause"}
{"cmd": "resume"}
{"cmd": "clear"}
{"cmd": "set_source", "kind": "file", "path": "D:/data/x.txt"}
{"cmd": "set_source", "kind": "serial", "serial_port": "COM3", "baudrate": 38400}
{"cmd": "set_source", "kind": "net", "host": "127.0.0.1", "port": 5000}
{"cmd": "set_decoder", "mode": "custom"}
{"cmd": "set_decoder", "mode": "pyais"}
{"cmd": "set_decoder", "mode": "compare"}
```

## 关键里程碑

| Day | 里程碑 | 状态 |
|-----|--------|------|
| Day 1 | 浏览器弹出地图页面 | OK |
| Day 2 | 地图上能看到首艘船舶 marker | OK |
| Day 2.5 | 多艘船舶动态刷新,侧边表格同步 | OK |
| Day 3 | 通过浏览器上传文件能切换数据源 | OK |
| Day 4 | 与 pyais 库对拍 4/4 误差 < 0.001° + WS 测试通过 | OK |
| Day 5 | 支持消息类型 1-5, 18-21, 24 + 双解码器 + 前端对比显示 | OK |

## 参考资料

- ITU-R M.1371-4 建议书
- [gpsd AIVDM/AIVDO 协议详解](https://gpsd.gitlab.io/gpsd/AIVDM.html)
- [libais C 参考实现 (bcl/aisparser)](https://github.com/bcl/aisparser)
- [pyais Python 参考实现](https://github.com/M0r13n/pyais)
- [Leaflet 文档](https://leafletjs.com/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
