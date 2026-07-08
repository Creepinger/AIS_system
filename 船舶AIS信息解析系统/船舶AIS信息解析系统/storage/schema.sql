-- SQLite 表结构
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
    utc_second  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ships_mmsi ON ships(mmsi);
CREATE INDEX IF NOT EXISTS idx_ships_ts ON ships(ts);