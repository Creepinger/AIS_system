"""MySQL 存储(可选后端)。"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from PySide6.QtCore import QObject, Slot

from ais.ais_ship import AIS_Ship


class MysqlStore(QObject):
    def __init__(self, host: str, port: int, user: str, password: str,
                 database: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        try:
            import mysql.connector
        except ImportError as e:
            raise RuntimeError(
                "请先安装 mysql-connector-python: pip install mysql-connector-python"
            ) from e

        # 确保数据库存在
        bootstrap = mysql.connector.connect(host=host, port=port,
                                            user=user, password=password)
        cur = bootstrap.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.close()
        bootstrap.close()

        self._conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password,
            database=database, autocommit=False,
        )
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ships (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                ts          DATETIME NOT NULL,
                mmsi        BIGINT NOT NULL,
                latitude    DOUBLE,
                longitude   DOUBLE,
                sog         DOUBLE,
                cog         INT,
                shipname    VARCHAR(40),
                msg_type    INT,
                utc_second  INT,
                INDEX idx_ships_mmsi (mmsi),
                INDEX idx_ships_ts (ts)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        self._conn.commit()

    @Slot(object)
    def insert(self, ship: AIS_Ship) -> None:
        ts = _dt.datetime.utcnow().replace(microsecond=0)
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO ships (ts, mmsi, latitude, longitude, sog, cog, "
            "shipname, msg_type, utc_second) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ts, ship.mmsi, ship.latitude, ship.longitude, ship.sog,
             ship.cog, ship.shipname, ship.msg_type, ship.utc_second),
        )
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass