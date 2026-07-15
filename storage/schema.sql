-- SQLite 表结构
-- 支持增量升级：已有表的机器再次运行时会自动 ALTER 新列
CREATE TABLE IF NOT EXISTS ships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    mmsi        INTEGER NOT NULL,
    latitude    REAL,
    longitude   REAL,
    sog         REAL,
    cog         INTEGER,
    shipname    TEXT,
    msg_type    INTEGER,
    utc_second  INTEGER,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_ships_mmsi ON ships(mmsi);
CREATE INDEX IF NOT EXISTS idx_ships_ts ON ships(ts);

-- 增量升级：老数据库没有 updated_at 列时补上
-- SQLite 不支持 IF NOT EXISTS ADD COLUMN，需要用 Python 迁移脚本处理
