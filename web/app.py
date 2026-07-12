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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

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
    # 默认加载真实 AIS 数据,快速回放(大量数据时请自行调整)
    sample_path = str(PROJECT_ROOT / "AIS one hour 202506.txt")
    await service.start("file", path=sample_path, line_delay_ms=1)
    log.info("AISService started with %s", sample_path)
    yield
    await service.stop()


app = FastAPI(title="船舶AIS信息解析系统", lifespan=lifespan)
# 不使用 app.mount("/static", StaticFiles(...)) —— Starlette 0.40 在 Python 3.13
# 下 FileResponse 的 Content-Length 与实际字节数不匹配，导致 JS 文件截断。
# 改用 StreamingResponse 流式发送，彻底绕开该 bug。
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
        headers={"Cache-Control": "public, max-age=3600"},
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

    # 根据 mode 选择解码器
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
                # 对比模式：使用专用接口
                cmp = decoder.decode_and_compare(raw)
                if cmp.success:
                    result_entry["success"] = True
                    result_entry["msg_type"] = cmp.msg_type
                    result_entry["mmsi"] = cmp.mmsi
                    if cmp.custom_ship:
                        result_entry["custom"] = cmp.custom_ship.to_dict()
                    if cmp.pyais_dict:
                        result_entry["pyais"] = cmp.pyais_dict
                    # 计算误差
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
                # 单一模式
                ship = AIS_Ship()
                rc = decoder.decode_nmea(raw, ship)
                if rc == 0:
                    result_entry["success"] = True
                    result_entry["msg_type"] = ship.msg_type
                    result_entry["mmsi"] = ship.mmsi
                    if mode == "custom":
                        result_entry["custom"] = ship.to_dict()
                    else:
                        # pyais 模式：从自研 ship 字段抽取标准化字典
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
