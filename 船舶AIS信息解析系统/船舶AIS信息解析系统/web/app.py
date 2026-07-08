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
from fastapi.responses import FileResponse, JSONResponse

from config import CONFIG, PROJECT_ROOT, DATA_DIR
from web.decoder_service import service
from web.ws import manager

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
    return FileResponse(str(fp))


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
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/favicon.ico")
async def favicon():
    ico = STATIC_DIR / "favicon.ico"
    if ico.exists():
        return FileResponse(str(ico))
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
