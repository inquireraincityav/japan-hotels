from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                added_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                hotel_id TEXT,
                hotel_name TEXT,
                source TEXT,
                room_bucket TEXT,
                total_cad REAL,
                total_jpy REAL,
                deeplink TEXT,
                raw TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_checks_ts ON checks(ts);
            CREATE TABLE IF NOT EXISTS last_alert (
                hotel_id TEXT PRIMARY KEY,
                total_cad REAL NOT NULL,
                ts REAL NOT NULL
            );
            """
        )


def add_chat(chat_id: int) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO chats(chat_id, added_at) VALUES (?, ?)",
            (chat_id, time.time()),
        )


def chat_ids() -> list[int]:
    with _lock, _conn() as c:
        return [r["chat_id"] for r in c.execute("SELECT chat_id FROM chats")]


def record_check(rows: list[dict]) -> None:
    if not rows:
        return
    ts = time.time()
    with _lock, _conn() as c:
        c.executemany(
            """INSERT INTO checks
               (ts, hotel_id, hotel_name, source, room_bucket,
                total_cad, total_jpy, deeplink, raw)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                (
                    ts,
                    r.get("hotel_id"),
                    r.get("hotel_name"),
                    r.get("source"),
                    r.get("room_bucket"),
                    r.get("total_cad"),
                    r.get("total_jpy"),
                    r.get("deeplink"),
                    r.get("raw"),
                )
                for r in rows
            ],
        )


def latest(limit: int = 10) -> list[dict]:
    with _lock, _conn() as c:
        cur = c.execute(
            """SELECT * FROM checks
               WHERE ts = (SELECT MAX(ts) FROM checks)
               ORDER BY total_cad ASC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def last_alert_cad(hotel_id: str) -> float | None:
    with _lock, _conn() as c:
        r = c.execute(
            "SELECT total_cad FROM last_alert WHERE hotel_id=?",
            (hotel_id,),
        ).fetchone()
        return r["total_cad"] if r else None


def set_last_alert(hotel_id: str, total_cad: float) -> None:
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO last_alert(hotel_id, total_cad, ts)
               VALUES (?,?,?)
               ON CONFLICT(hotel_id) DO UPDATE SET
                 total_cad=excluded.total_cad, ts=excluded.ts""",
            (hotel_id, total_cad, time.time()),
        )
