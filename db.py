# db.py
# Simple per-user storage using SQLite (async) via aiosqlite.
# NOTE: On free Render, filesystem can be ephemeral. For true persistence,
# switch to Postgres later. This is a clean starter that "just works".

from __future__ import annotations

import aiosqlite
from typing import Optional, List, Tuple

DB_PATH = "bot.db"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  lang TEXT NOT NULL DEFAULT 'fa'
);

CREATE TABLE IF NOT EXISTS words (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  word TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, word)
);

CREATE TABLE IF NOT EXISTS user_state (
  user_id INTEGER PRIMARY KEY,
  state TEXT NOT NULL DEFAULT ''
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


async def ensure_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id, lang) VALUES (?, 'fa')", (user_id,))
        await db.execute("INSERT OR IGNORE INTO user_state(user_id, state) VALUES (?, '')", (user_id,))
        await db.commit()


async def get_lang(user_id: int) -> str:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return (row[0] if row else "fa") or "fa"


async def set_lang(user_id: int, lang: str) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        await db.commit()


async def set_state(user_id: int, state: str) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_state SET state=? WHERE user_id=?", (state, user_id))
        await db.commit()


async def get_state(user_id: int) -> str:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT state FROM user_state WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return (row[0] if row else "") or ""


async def clear_state(user_id: int) -> None:
    await set_state(user_id, "")


async def add_word(user_id: int, word: str) -> bool:
    await ensure_user(user_id)
    w = word.strip()
    if not w:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO words(user_id, word) VALUES (?, ?)", (user_id, w))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Already exists (UNIQUE(user_id, word))
            return False


async def list_words(user_id: int, limit: int = 200) -> List[str]:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT word FROM words WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def delete_word(user_id: int, word: str) -> int:
    await ensure_user(user_id)
    w = word.strip()
    if not w:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM words WHERE user_id=? AND word=?", (user_id, w))
        await db.commit()
        return cur.rowcount or 0


async def delete_all_words(user_id: int) -> int:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM words WHERE user_id=?", (user_id,))
        await db.commit()
        return cur.rowcount or 0
