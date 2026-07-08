"""船舶AIS信息解析系统 - Web 入口。

启动 FastAPI + uvicorn,默认在 http://127.0.0.1:8000 提供服务,
浏览器打开后可看到 Leaflet 地图 + 实时船舶 marker。

Usage:
    python main.py                                  # 默认 http://127.0.0.1:8000
    python main.py --port 9000                      # 自定义端口
    python main.py --reload                         # 开发热重载
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys

from config import CONFIG


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="船舶AIS Web 可视化系统")
    p.add_argument("--host", default=CONFIG.web.host)
    p.add_argument("--port", type=int, default=CONFIG.web.port)
    p.add_argument("--reload", action="store_true",
                   help="开发模式:文件变更自动重载 (需 watchfiles)")
    p.add_argument("--log-level", default="info",
                   choices=("debug", "info", "warning", "error"))
    return p.parse_args()


def check_port_available(host: str, port: int) -> tuple[bool, str | None]:
    """Return whether uvicorn can bind the requested TCP endpoint."""
    if port == 0:
        return True, None

    try:
        addr_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        return False, f"无法解析主机 {host!r}: {e}"

    last_error: OSError | None = None
    for family, socktype, proto, _, sockaddr in addr_infos:
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.bind(sockaddr)
        except OSError as e:
            last_error = e
            continue
        return True, None

    return False, str(last_error) if last_error else "端口不可用"


def main() -> int:
    args = parse_args()
    try:
        import uvicorn
    except ImportError as e:
        print(f"[ERR] 需要 uvicorn: pip install 'uvicorn[standard]'\n  {e}",
              file=sys.stderr)
        return 2

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    available, reason = check_port_available(args.host, args.port)
    if not available:
        print(f"[ERR] 无法启动 Web 服务: {args.host}:{args.port} 已被占用或不可绑定。", file=sys.stderr)
        if reason:
            print(f"      原因: {reason}", file=sys.stderr)
        print("      解决办法:", file=sys.stderr)
        print("        1. 换一个端口: python main.py --port 9000", file=sys.stderr)
        print("        2. Windows 查看占用进程:", file=sys.stderr)
        print(f"           Get-NetTCPConnection -LocalPort {args.port} | Select-Object LocalAddress,LocalPort,State,OwningProcess", file=sys.stderr)
        print("           Stop-Process -Id <OwningProcess>", file=sys.stderr)
        return 1

    print(f"启动 Web 服务: http://{args.host}:{args.port}")
    print("打开浏览器访问即可。Ctrl-C 退出。")

    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
