"""Web 前端: FastAPI + Leaflet + WebSocket。"""
from . import ws, decoder_service, link_async, app

__all__ = ["ws", "decoder_service", "link_async", "app"]


def get_app():
    """工厂函数:uvicorn 启动用。"""
    return app.app
