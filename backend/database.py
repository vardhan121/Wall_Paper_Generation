from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from config import CFG, DB, WALLPAPERS

DB_LOCK = threading.Lock()


def db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK:
        conn = db()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            summary TEXT NOT NULL,
            visual_memory TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            prompt TEXT NOT NULL,
            image_path TEXT NOT NULL
        );
        """)
        conn.commit()
        conn.close()


def now():
    return time.time()


def recent_activity(hours: int) -> list[dict[str, Any]]:
    cutoff = now() - hours * 3600
    return activity_since(cutoff)


def activity_since(timestamp: float) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = db()
        rows = conn.execute(
            "SELECT * FROM activity WHERE ts > ? ORDER BY ts ASC", (timestamp,)
        ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def all_visual_memory() -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = db()
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY created_at ASC"
        ).fetchall()
        conn.close()
    return [dict(row) for row in rows]


def latest_memory_keywords() -> list[str]:
    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT visual_memory FROM memories ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    if not row:
        return []
    try:
        visual_memory = json.loads(row["visual_memory"])
    except (TypeError, json.JSONDecodeError):
        return []
    keywords = visual_memory.get("keywords", [])
    if not isinstance(keywords, list):
        return []
    return [
        keyword.strip()
        for keyword in keywords
        if isinstance(keyword, str) and keyword.strip()
    ]


def memory_token_stats() -> dict[str, Any]:
    rows = all_visual_memory()
    details = []
    total_characters = 0
    total_tokens = 0
    for row in rows:
        text = f'{row["summary"]}\n{row["visual_memory"]}'
        characters = len(text)
        tokens = max(0, round(characters / 4))
        total_characters += characters
        total_tokens += tokens
        details.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "characters": characters,
            "estimated_tokens": tokens,
        })
    return {
        "memory_count": len(rows),
        "total_characters": total_characters,
        "estimated_tokens": total_tokens,
        "method": "approximately 1 token per 4 characters; model tokenizer may differ",
        "rows": details,
    }


def last_generation_time():
    with DB_LOCK:
        conn = db()
        row = conn.execute(
            "SELECT created_at FROM generations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    return row["created_at"] if row else 0


def prune_retained_data(conn):
    conn.execute(
        "DELETE FROM activity WHERE id NOT IN "
        "(SELECT id FROM activity ORDER BY ts DESC LIMIT ?)",
        (int(CFG["max_activity_records"]),),
    )
    conn.execute(
        "DELETE FROM memories WHERE id NOT IN "
        "(SELECT id FROM memories ORDER BY created_at DESC LIMIT ?)",
        (int(CFG["max_memory_records"]),),
    )
    old_paths = conn.execute(
        "SELECT image_path FROM generations WHERE id NOT IN "
        "(SELECT id FROM generations ORDER BY created_at DESC LIMIT ?)",
        (int(CFG["max_generation_records"]),),
    ).fetchall()
    conn.execute(
        "DELETE FROM generations WHERE id NOT IN "
        "(SELECT id FROM generations ORDER BY created_at DESC LIMIT ?)",
        (int(CFG["max_generation_records"]),),
    )
    return [Path(row["image_path"]) for row in old_paths]


def delete_old_wallpapers(paths):
    for path in paths:
        try:
            path.resolve().relative_to(WALLPAPERS.resolve())
        except ValueError:
            continue
        if path.is_file():
            path.unlink()
