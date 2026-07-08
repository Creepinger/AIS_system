"""全局配置。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class SerialConfig:
    port: str = "COM3"
    baudrate: int = 38400
    bytesize: int = 8
    parity: str = "N"  # N, E, O, M, S
    stopbits: float = 1


@dataclass
class NetworkConfig:
    host: str = "127.0.0.1"
    port: int = 5000
    reconnect_sec: float = 3.0


@dataclass
class FileConfig:
    path: str = str(PROJECT_ROOT / "tests" / "samples" / "sample_nmea.txt")
    line_delay_ms: int = 30


@dataclass
class DbConfig:
    backend: str = "sqlite"  # sqlite | mysql
    sqlite_path: str = str(DATA_DIR / "ais.db")
    mysql_host: str = os.environ.get("AIS_MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.environ.get("AIS_MYSQL_PORT", "3306"))
    mysql_user: str = os.environ.get("AIS_MYSQL_USER", "root")
    mysql_password: str = os.environ.get("AIS_MYSQL_PASSWORD", "")
    mysql_database: str = os.environ.get("AIS_MYSQL_DB", "ais")


@dataclass
class UiConfig:
    window_width: int = 1200
    window_height: int = 800
    table_max_rows: int = 500
    grid_size: int = 8  # 8x8 网格
    grid_step_deg: float = 0.5  # 每格 0.5 度


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    broadcast_interval_ms: int = 200
    max_clients: int = 32
    default_tile: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"


@dataclass
class AppConfig:
    serial: SerialConfig = field(default_factory=SerialConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    file: FileConfig = field(default_factory=FileConfig)
    db: DbConfig = field(default_factory=DbConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    web: WebConfig = field(default_factory=WebConfig)


CONFIG = AppConfig()