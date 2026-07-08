"""SQLite 存储(默认后端)。"""
from __future__ import annotations

import datetime as _dt
import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from ais.ais_ship import AIS_Ship


class SqliteStore(QObject):
    def __init__(self, path: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    @Slot(object)
    def insert(self, ship: AIS_Ship) -> None:
        ts = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self._conn.execute(
            "INSERT INTO ships (ts, mmsi, latitude, longitude, sog, cog, "
            "shipname, msg_type, utc_second) VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, ship.mmsi, ship.latitude, ship.longitude, ship.sog,
             ship.cog, ship.shipname, ship.msg_type, ship.utc_second),
        )
        self._conn.commit()

    def query_recent(self, limit: int = 100) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM ships ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass