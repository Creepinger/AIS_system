"""FastAPI 应用入口。

提供:
- `GET /`           → 返回 web/static/index.html
- `GET /healthz`    → 健康检查
- `POST /api/load`  → 上传文件后切换数据源
- `WS  /ws`         → WebSocket 双向通道(收命令 + 推实时)

lifespan 中自动启动 AISService。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# 确保无论以何种方式启动(web.app / python -m web.app / uvicorn web.app:app)
# 都能找到项目根目录下的 config.py / ais / web 包。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException,
)
from fastapi.responses import JSONResponse, StreamingResponse

from config import CONFIG, PROJECT_ROOT, DATA_DIR
from web.decoder_service import service
from web.ws import manager
from ais.unified_decoder import UnifiedDecoder, DecoderType
from ais.ais_ship import AIS_Ship

log = logging.getLogger("uvicorn.error")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")


HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from storage.fastapi_store import FastSqliteStore
    service._store = FastSqliteStore(CONFIG.db.sqlite_path)
    log.info("数据库已启用: %s", CONFIG.db.sqlite_path)
    sample_path = CONFIG.file.path
    await service.start("file", path=sample_path, line_delay_ms=CONFIG.file.line_delay_ms)
    log.info("AISService started with %s", sample_path)
    yield
    await service.stop()
    service._store.close()
    service._store = None


app = FastAPI(title="船舶AIS信息解析系统", lifespan=lifespan)
# 不使用 app.mount("/static", StaticFiles(...)) —— Starlette 0.40 在 Python 3.13
# 下处理 /static 路由时会抛 "Response content longer than Content-Length",
# 导致 map.js 等静态文件加载不完整,前端地图空白。
# 改用手写路由 + FileResponse 直接发送文件,彻底绕开该 bug。
STATIC_ROOT = STATIC_DIR.resolve()


def _safe_static(path: str) -> Path:
    """解析并校验路径,防止 ../ 越权访问 STATIC_DIR 之外的资源。"""
    candidate = (STATIC_ROOT / path).resolve()
    try:
        candidate.relative_to(STATIC_ROOT)
    except ValueError:
        raise HTTPException(404, "not found")
    if not candidate.is_file():
        raise HTTPException(404, "not found")
    return candidate


@app.get("/static/{path:path}")
async def static_handler(path: str):
    fp = _safe_static(path)
    media_type = _guess_media_type(fp.name)
    return StreamingResponse(
        _stream_file(fp),
        media_type=media_type,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


async def _stream_file(fp: Path, chunk_size: int = 64 * 1024):
    with open(fp, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def _guess_media_type(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower()
    return {
        "html": "text/html; charset=utf-8",
        "css": "text/css",
        "js": "application/javascript",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "svg": "image/svg+xml",
        "ico": "image/x-icon",
        "woff2": "font/woff2",
        "woff": "font/woff",
        "ttf": "font/ttf",
    }.get(ext, "application/octet-stream")


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "service_source": service.source_desc,
        "ship_count": len(service.ships),
        "ws_clients": manager.client_count,
    }


@app.get("/")
async def index():
    return await static_handler("index.html")


@app.get("/parse")
async def parse_page():
    """AIS 在线解析页面。

    用户可以在页面粘贴 NMEA 报文并立即解码（支持多条）。
    """
    return await static_handler("parse.html")


@app.get("/analytics")
async def analytics_page():
    """AIS 规律分析页面。

    5 个 Tab:
      1. 总览 / 类型分布
      2. 时间分布
      3. 空间分布（船舶聚集地）
      4. 航速 / 航向
      5. 异常检测
    """
    return await static_handler("analytics.html")


@app.post("/api/parse_text")
async def api_parse_text(payload: dict):
    """解析用户提交的 NMEA 文本。

    请求 JSON:
    ```
    {
        "lines": ["!AIVDM,...", "!AIVDM,..."],
        "mode": "custom" | "pyais" | "compare"
    }
    ```

    返回 JSON:
    ```
    {
        "results": [
            {
                "success": true,
                "msg_type": 1,
                "mmsi": "413318730",
                "raw": "!AIVDM...",
                "custom": {...} | null,
                "pyais": {...} | null,
                "errors": {"lat":0,"lon":0,"sog":0,"cog":0} | null,
                "error": "" | "失败原因"
            }, ...
        ]
    }
    ```
    """
    lines = payload.get("lines") or []
    mode = payload.get("mode") or "custom"

    if not isinstance(lines, list):
        raise HTTPException(400, "lines 必须是字符串数组")

    if mode not in ("custom", "pyais", "compare"):
        raise HTTPException(400, f"未知 mode: {mode}")

    decoder_type = {
        "custom": DecoderType.CUSTOM,
        "pyais": DecoderType.PYAIS,
        "compare": DecoderType.BOTH,
    }[mode]

    decoder = UnifiedDecoder(decoder_type)
    results = []

    for raw in lines:
        raw = (raw or "").strip()
        if not raw:
            continue

        result_entry: dict = {
            "success": False,
            "msg_type": 0,
            "mmsi": 0,
            "raw": raw,
            "custom": None,
            "pyais": None,
            "errors": None,
            "error": "",
        }

        try:
            if mode == "compare":
                cmp = decoder.decode_and_compare(raw)
                if cmp.success:
                    result_entry["success"] = True
                    result_entry["msg_type"] = cmp.msg_type
                    result_entry["mmsi"] = cmp.mmsi
                    if cmp.custom_ship:
                        result_entry["custom"] = cmp.custom_ship.to_dict()
                    if cmp.pyais_dict:
                        result_entry["pyais"] = cmp.pyais_dict
                    if cmp.custom_ship and cmp.pyais_dict:
                        result_entry["errors"] = {
                            "lat": round(abs(cmp.custom_ship.latitude - (cmp.pyais_dict.get("lat") or 0)), 6),
                            "lon": round(abs(cmp.custom_ship.longitude - (cmp.pyais_dict.get("lon") or 0)), 6),
                            "sog": round(abs(cmp.custom_ship.sog - (cmp.pyais_dict.get("speed") or 0)), 2),
                            "cog": round(min(
                                abs(cmp.custom_ship.cog - (cmp.pyais_dict.get("course") or 0)),
                                360 - abs(cmp.custom_ship.cog - (cmp.pyais_dict.get("course") or 0))
                            ), 2),
                        }
                else:
                    result_entry["error"] = cmp.error_msg or "解码失败"
            else:
                ship = AIS_Ship()
                rc = decoder.decode_nmea(raw, ship)
                if rc == 0:
                    result_entry["success"] = True
                    result_entry["msg_type"] = ship.msg_type
                    result_entry["mmsi"] = ship.mmsi
                    if mode == "custom":
                        result_entry["custom"] = ship.to_dict()
                    else:
                        result_entry["pyais"] = ship.to_dict()
                else:
                    result_entry["error"] = "解码失败"
        except Exception as e:
            log.warning("parse_text failed: %s", e)
            result_entry["error"] = str(e)

        results.append(result_entry)

    return {"ok": True, "count": len(results), "results": results}


@app.get("/favicon.ico")
async def favicon():
    ico = STATIC_DIR / "favicon.ico"
    if ico.exists():
        return await static_handler("favicon.ico")
    return JSONResponse(status_code=204, content=None)


@app.post("/api/load")
async def api_load(kind: str = Form("file"),
                   path: str | None = Form(None),
                   upload: Optional[UploadFile] = File(None)):
    """切换数据源。

    - `kind=file` + `path`:加载本地文件
    - `kind=file` + `upload`:上传新文件,保存到 data/uploads 后加载
    - `kind=serial`:需要 port / baudrate 表单字段
    - `kind=net`:需要 host / port 表单字段
    """
    if kind == "file":
        if upload is not None:
            upload_dir = DATA_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            save_path = upload_dir / upload.filename
            with open(save_path, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            path = str(save_path)
        if not path or not Path(path).exists():
            raise HTTPException(400, f"文件不存在: {path}")
        await service.handle_command({"cmd": "set_source", "kind": "file", "path": path})
    elif kind == "net":
        # 简化:path 为 "host:port"
        if not path or ":" not in path:
            raise HTTPException(400, "net 模式需要 host:port")
        host, pstr = path.split(":", 1)
        await service.handle_command({
            "cmd": "set_source", "kind": "net",
            "host": host, "port": int(pstr),
        })
    else:
        raise HTTPException(400, f"未知 kind: {kind}")
    return {"ok": True, "source": service.source_desc}


@app.get("/api/db/count")
async def api_db_count():
    """返回数据库中船舶记录总数。"""
    return {"count": service._store.ship_count()}


@app.get("/api/ships/query")
async def api_ships_query(
    mmsi: str | None = None,
    latitude: str | None = None,
    longitude: str | None = None,
    sog: str | None = None,
    cog: str | None = None,
    shipname: str | None = None,
    limit: int = 1000,
):
    """多字段模糊查询，空字段自动忽略。"""
    rows = service._store.query_like(
        mmsi=mmsi, latitude=latitude, longitude=longitude,
        sog=sog, cog=cog, shipname=shipname, limit=limit,
    )
    return {"ok": True, "count": len(rows), "ships": rows}


@app.get("/api/ships/recent")
async def api_ships_recent(limit: int = 100):
    """查询最近的船舶记录（按时间倒序）。"""
    rows = service._store.query_recent(limit=limit)
    return {"ok": True, "count": len(rows), "ships": rows}


@app.get("/api/ships/{mmsi}")
async def api_ships_by_mmsi(mmsi: int, limit: int = 100):
    """查询指定 MMSI 的所有历史记录。"""
    rows = service._store.query_by_mmsi(mmsi, limit=limit)
    return {"ok": True, "mmsi": mmsi, "count": len(rows), "ships": rows}


@app.post("/api/ships")
async def api_ship_create(payload: dict):
    """新增一条船舶记录（手动录入）。"""
    required = ["mmsi"]
    for f in required:
        if f not in payload or payload[f] is None:
            raise HTTPException(400, f"缺少必填字段: {f}")
    from ais.ais_ship import AIS_Ship
    ship = AIS_Ship(
        mmsi=int(payload["mmsi"]),
        latitude=float(payload.get("latitude", 0)),
        longitude=float(payload.get("longitude", 0)),
        sog=float(payload.get("sog", 0)),
        cog=int(payload.get("cog", 0)),
        shipname=str(payload.get("shipname", "")),
        msg_type=int(payload.get("msg_type", 0)),
        utc_second=int(payload.get("utc_second", -1)),
    )
    row_id = service._store.insert(ship)
    return {"ok": True, "id": row_id}


@app.put("/api/ships/{row_id:int}")
async def api_ship_update(row_id: int, payload: dict):
    """更新指定记录的可编辑字段（MMSI/纬度/经度/航速/航向/船名）。"""
    ok = service._store.update(row_id, payload)
    if not ok:
        raise HTTPException(404, f"记录 {row_id} 不存在或无有效字段更新")
    return {"ok": True, "id": row_id}


@app.delete("/api/ships/{row_id:int}")
async def api_ship_delete(row_id: int):
    """删除指定记录。"""
    ok = service._store.delete(row_id)
    if not ok:
        raise HTTPException(404, f"记录 {row_id} 不存在")
    return {"ok": True, "id": row_id}


@app.delete("/api/ships")
async def api_ships_delete_all():
    """清空全部记录。"""
    count = service._store.delete_all()
    return {"ok": True, "deleted": count}


@app.post("/api/db/toggle")
async def api_db_toggle():
    """切换数据库启用状态（已废弃，数据库始终启用）。"""
    return {"enabled": True, "path": CONFIG.db.sqlite_path}


# ──────────────────────────────────────────────────────────────
# AIS 规律分析：5 个统计/可视化端点
# ──────────────────────────────────────────────────────────────


@app.get("/api/analytics/overview")
async def api_analytics_overview():
    """总体概览：消息总数 / 独立船舶数 / 时间范围 / 今日消息数。"""
    return service._store.analytics_overview()


@app.get("/api/analytics/msg-types")
async def api_analytics_msg_types():
    """消息类型分布（AIS 类型 1~27）。"""
    return {"rows": service._store.analytics_msg_type_distribution()}


@app.get("/api/analytics/temporal")
async def api_analytics_temporal(bucket_minutes: int = 5):
    """时间序列：可配置桶大小（分钟）。"""
    return service._store.analytics_temporal_series(bucket_minutes)


@app.get("/api/analytics/hourly-heatmap")
async def api_analytics_hourly_heatmap():
    """7×24 小时×星期 热力矩阵。"""
    grid = service._store.analytics_hourly_heatmap()
    return {"grid": grid, "days": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}


@app.get("/api/analytics/top-ships")
async def api_analytics_top_ships(limit: int = 20):
    """活跃船舶 Top N。"""
    return {"rows": service._store.analytics_top_ships(limit)}


@app.get("/api/analytics/speed-distribution")
async def api_analytics_speed():
    """航速直方图（5 节桶）。"""
    return {"rows": service._store.analytics_speed_distribution()}


@app.get("/api/analytics/course-distribution")
async def api_analytics_course():
    """航向 16 方位。"""
    return {"rows": service._store.analytics_course_distribution()}


@app.get("/api/analytics/geo-grid")
async def api_analytics_geo_grid(precision: int = 2, top: int = 200):
    """地理网格热度，按 lat/lon 精度聚合 top N。"""
    return {"rows": service._store.analytics_geo_grid(precision, top)}


@app.get("/api/analytics/anomalies")
async def api_analytics_anomalies():
    """异常检测：无效坐标/部分解码/异常速度/位置跳变。"""
    return service._store.analytics_anomalies()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except json.JSONDecodeError:
                continue
            await service.handle_command(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WS exception: %s", e)
    finally:
        manager.disconnect(ws)
