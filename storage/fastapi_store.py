"""FastAPI 专用 SQLite 存储后端（线程安全）。"""
from __future__ import annotations

import datetime as _dt
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from ais.ais_ship import AIS_Ship


class FastSqliteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """增量升级：给老数据库补上新列。"""
        with self._lock:
            cur = self._conn.execute("PRAGMA table_info(ships)")
            cols = {row[1] for row in cur.fetchall()}
            if "updated_at" not in cols:
                self._conn.execute(
                    "ALTER TABLE ships ADD COLUMN updated_at TEXT"
                )
                self._conn.commit()

    # ─── Insert ────────────────────────────────────────────────

    def insert(self, ship: AIS_Ship) -> int:
        ts = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO ships (ts, mmsi, latitude, longitude, sog, cog, "
                "shipname, msg_type, utc_second, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts, ship.mmsi, ship.latitude, ship.longitude, ship.sog,
                 ship.cog, ship.shipname, ship.msg_type, ship.utc_second, None),
            )
            self._conn.commit()
            return cur.lastrowid

    # ─── Query ────────────────────────────────────────────────

    def query_recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ships ORDER BY id DESC LIMIT ?", (limit,)
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def query_by_mmsi(self, mmsi: int, limit: int = 100) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ships WHERE mmsi = ? ORDER BY id DESC LIMIT ?",
                (mmsi, limit),
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def query_like(
        self,
        mmsi: str | None = None,
        latitude: str | None = None,
        longitude: str | None = None,
        sog: str | None = None,
        cog: str | None = None,
        shipname: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """多字段模糊查询。空参数自动忽略，仅匹配有值的字段。"""
        conditions, params = [], []
        if mmsi:
            conditions.append("CAST(mmsi AS TEXT) LIKE ?")
            params.append(f"%{mmsi}%")
        if latitude:
            conditions.append("CAST(latitude AS TEXT) LIKE ?")
            params.append(f"%{latitude}%")
        if longitude:
            conditions.append("CAST(longitude AS TEXT) LIKE ?")
            params.append(f"%{longitude}%")
        if sog:
            conditions.append("CAST(sog AS TEXT) LIKE ?")
            params.append(f"%{sog}%")
        if cog:
            conditions.append("CAST(cog AS TEXT) LIKE ?")
            params.append(f"%{cog}%")
        if shipname:
            conditions.append("shipname LIKE ?")
            params.append(f"%{shipname}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM ships {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def query_all(self, limit: int = 1000) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ships ORDER BY id DESC LIMIT ?", (limit,)
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def get_by_id(self, row_id: int) -> Optional[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ships WHERE id = ?", (row_id,)
            )
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
        return dict(zip(cols, row)) if row else None

    # ─── Update ──────────────────────────────────────────────

    def update(self, row_id: int, fields: dict) -> bool:
        """更新指定行的可编辑字段，返回是否成功。"""
        editable = {"mmsi", "latitude", "longitude", "sog", "cog", "shipname"}
        updates = {k: v for k, v in fields.items() if k in editable}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        updates["updated_at"] = _dt.datetime.utcnow().isoformat(
            timespec="seconds"
        ) + "Z"
        set_clause += ", updated_at = ?"
        values = list(updates.values()) + [row_id]
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE ships SET {set_clause} WHERE id = ?", values
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ─── Delete ──────────────────────────────────────────────

    def delete(self, row_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM ships WHERE id = ?", (row_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def delete_all(self) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM ships")
            self._conn.commit()
            return cur.rowcount

    # ─── Stats ────────────────────────────────────────────────

    def ship_count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM ships")
            return cur.fetchone()[0]

    # ─── Analytics ───────────────────────────────────────────

    def analytics_overview(self) -> dict:
        """总体概览：消息总数/船舶数/时间范围/今日数。"""
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM ships").fetchone()[0]
            ship_cnt = self._conn.execute(
                "SELECT COUNT(DISTINCT mmsi) FROM ships"
            ).fetchone()[0]
            row = self._conn.execute(
                "SELECT MIN(ts), MAX(ts) FROM ships"
            ).fetchone()
            earliest, latest = row[0], row[1]
            # 今日（UTC 日期维度）消息数：取 MAX(ts) 同一天内的消息数
            today_cnt = 0
            if latest:
                latest_date = latest[:10]  # 'YYYY-MM-DD'
                today_cnt = self._conn.execute(
                    "SELECT COUNT(*) FROM ships WHERE substr(ts,1,10) = ?",
                    (latest_date,),
                ).fetchone()[0]
        return {
            "total": total,
            "ship_count": ship_cnt,
            "earliest": earliest,
            "latest": latest,
            "today": today_cnt,
        }

    def analytics_msg_type_distribution(self) -> list[dict]:
        """消息类型分布（AIS 消息类型 1~27）。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT msg_type, COUNT(*) AS n FROM ships "
                "GROUP BY msg_type ORDER BY msg_type"
            )
            rows = cur.fetchall()
        return [
            {"msg_type": int(r[0]) if r[0] is not None else -1, "count": int(r[1])}
            for r in rows
        ]

    def analytics_temporal_series(self, bucket_minutes: int = 5) -> dict:
        """时间分布：按可配置时间桶聚合消息数（AIS 数据通常没有秒级时间戳，按 ts 走）。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT ts, msg_type FROM ships ORDER BY id ASC"
            )
            entries = cur.fetchall()
        if not entries:
            return {"buckets": [], "by_type": {}}

        from collections import defaultdict, Counter
        import datetime as _dt

        bucket_sec = bucket_minutes * 60
        ts_map: dict[int, Counter] = defaultdict(Counter)

        for ts, mt in entries:
            try:
                dt = _dt.datetime.fromisoformat(ts.rstrip("Z"))
            except Exception:
                continue
            bucket = int(dt.timestamp() // bucket_sec) * bucket_sec
            ts_map[bucket][mt] += 1

        buckets = sorted(ts_map.keys())
        labels = [
            _dt.datetime.fromtimestamp(b, tz=_dt.timezone.utc).strftime(
                "%m-%d %H:%M"
            )
            for b in buckets
        ]
        total_per_bucket = [sum(ts_map[b].values()) for b in buckets]

        # 收集所有出现过的 msg_type
        all_types = sorted({mt for ctr in ts_map.values() for mt in ctr})

        by_type = {
            str(mt): [
                ts_map[b].get(mt, 0) for b in buckets
            ]
            for mt in all_types
        }
        return {
            "labels": labels,
            "totals": total_per_bucket,
            "by_type": by_type,
            "bucket_minutes": bucket_minutes,
        }

    def analytics_hourly_heatmap(self) -> list[list[int]]:
        """小时×星期分布热力图：行=星期(0=周一)，列=小时。"""
        import datetime as _dt
        from collections import defaultdict
        grid: dict[tuple[int, int], int] = defaultdict(int)
        with self._lock:
            cur = self._conn.execute("SELECT ts FROM ships")
            for (ts,) in cur.fetchall():
                try:
                    dt = _dt.datetime.fromisoformat(ts.rstrip("Z"))
                except Exception:
                    continue
                grid[(dt.weekday(), dt.hour)] += 1
        # 输出 7×24
        return [
            [grid.get((d, h), 0) for h in range(24)]
            for d in range(7)
        ]

    def analytics_top_ships(self, limit: int = 20) -> list[dict]:
        """活跃船舶 Top N：按消息数降序。"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT mmsi, COUNT(*) AS n, "
                "MIN(ts) AS first_seen, MAX(ts) AS last_seen "
                "FROM ships GROUP BY mmsi ORDER BY n DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "mmsi": int(r[0]),
                "count": int(r[1]),
                "first_seen": r[2],
                "last_seen": r[3],
            }
            for r in rows
        ]

    def analytics_speed_distribution(self) -> list[dict]:
        """速度分布直方图（按 5 节桶）。"""
        from collections import defaultdict
        buckets: dict[int, int] = defaultdict(int)
        with self._lock:
            cur = self._conn.execute(
                "SELECT sog FROM ships WHERE sog IS NOT NULL"
            )
            for (sog,) in cur.fetchall():
                if sog is None:
                    continue
                # 每 5 节一桶，0~100
                b = min(100, max(0, int(sog // 5) * 5))
                buckets[b] += 1
        return [
            {"bucket": b, "count": buckets[b]}
            for b in sorted(buckets.keys())
        ]

    def analytics_course_distribution(self) -> list[dict]:
        """航向玫瑰图：按 30° 桶分。"""
        from collections import defaultdict
        buckets: dict[int, int] = defaultdict(int)
        with self._lock:
            cur = self._conn.execute(
                "SELECT cog FROM ships WHERE cog IS NOT NULL"
            )
            for (cog,) in cur.fetchall():
                if cog is None:
                    continue
                b = (int(cog) % 360) // 30
                buckets[b] += 1
        labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return [
            {"dir": labels[b], "deg_start": b * 30, "count": buckets[b]}
            for b in range(16)
        ]

    def analytics_geo_grid(self, precision: int = 2, top: int = 200) -> list[dict]:
        """地理网格热力：按精度（degree）聚合 (lat, lon) 桶，SQL 内完成避免大量回传。"""
        p = 10 ** precision
        with self._lock:
            cur = self._conn.execute(
                f"SELECT ROUND(latitude, ?) AS lat, ROUND(longitude, ?) AS lon, "
                f"COUNT(*) AS n "
                f"FROM ships "
                f"WHERE latitude IS NOT NULL AND longitude IS NOT NULL "
                f"GROUP BY lat, lon "
                f"ORDER BY n DESC LIMIT ?",
                (precision, precision, top),
            )
            rows = cur.fetchall()
        return [
            {"lat": float(r[0]) if r[0] is not None else 0,
             "lon": float(r[1]) if r[1] is not None else 0,
             "count": int(r[2])}
            for r in rows
        ] 

    def analytics_anomalies(self) -> dict:
        """异常检测:
        - 无效坐标（0,0）
        - 缺失坐标但有其他字段
        - 异常速度 (>40 节)
        - 跳跃的 MMSI（同 MMSI、相邻 5 分钟内、距离 >50 km，疑似伪造或跳变)
        """
        import math
        bad_loc: list[dict] = []
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, mmsi, ts, latitude, longitude, sog, msg_type FROM ships"
            )
            rows = [dict(id=r[0], mmsi=r[1], ts=r[2],
                         latitude=r[3], longitude=r[4],
                         sog=r[5], msg_type=r[6]) for r in cur.fetchall()]

        # 无效坐标（0,0）
        for r in rows:
            if r["latitude"] == 0 and r["longitude"] == 0:
                bad_loc.append({**r, "reason": "坐标位于 (0,0)，疑似无效"})

        # 缺失坐标但有其它字段（说明消息部分解析成功，但定位失败）
        partial = []
        for r in rows:
            if (r["latitude"] is None or r["longitude"] is None) and r["mmsi"]:
                partial.append({**r, "reason": "坐标缺失但 MMSI 存在"})

        # 异常速度
        abnormal_speed = []
        for r in rows:
            if r["sog"] is not None and r["sog"] > 40:
                abnormal_speed.append({**r, "reason": f"航速 {r['sog']:.1f} 节 超过 40 节限值"})

        # 跳跃定位：同 MMSI 按时间排序，相邻 >50km
        from collections import defaultdict
        per_mmsi: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            if r["latitude"] is None or r["longitude"] is None:
                continue
            per_mmsi[r["mmsi"]].append(r)
        jumps = []
        for mmsi, lst in per_mmsi.items():
            lst.sort(key=lambda x: x["ts"] or "")
            for i in range(1, len(lst)):
                a, b = lst[i - 1], lst[i]
                try:
                    import datetime as _dt
                    ta = _dt.datetime.fromisoformat((a["ts"] or "").rstrip("Z"))
                    tb = _dt.datetime.fromisoformat((b["ts"] or "").rstrip("Z"))
                    dt_min = abs((tb - ta).total_seconds()) / 60
                except Exception:
                    continue
                if dt_min <= 0 or dt_min > 30:
                    continue
                # haversine 距离
                lat1, lon1 = math.radians(a["latitude"]), math.radians(a["longitude"])
                lat2, lon2 = math.radians(b["latitude"]), math.radians(b["longitude"])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                km = 6371 * 2 * math.asin(math.sqrt(h))
                if km > 50:
                    jumps.append({
                        "mmsi": mmsi,
                        "ts_a": a["ts"],
                        "ts_b": b["ts"],
                        "lat_a": a["latitude"],
                        "lon_a": a["longitude"],
                        "lat_b": b["latitude"],
                        "lon_b": b["longitude"],
                        "km": round(km, 1),
                        "reason": f"30 分钟内跨越 {km:.1f} km",
                    })

        # 每类只取前 20 条，避免响应过大
        return {
            "invalid_location": bad_loc[:20],
            "partial_decode": partial[:20],
            "abnormal_speed": abnormal_speed[:20],
            "location_jumps": jumps[:20],
            "summary": {
                "invalid_location_count": len(bad_loc),
                "partial_decode_count": len(partial),
                "abnormal_speed_count": len(abnormal_speed),
                "location_jumps_count": len(jumps),
            },
        }

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
