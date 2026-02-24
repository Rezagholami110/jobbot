#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jobs.py - Telegram keyword monitor bot (single-file, Render-friendly)

✅ Works without python-telegram-bot (no v13/v20 confusion)
✅ Uses raw Telegram HTTP API + getUpdates polling
✅ Keeps Render service alive with HTTP server on PORT
✅ Commands:
   /start
   /add <keyword>
   /remove <keyword>
   /list
✅ Monitors Google News RSS for each user's keywords and notifies on new items

ENV required:
  BOT_TOKEN = "<telegram bot token>"

Optional ENV:
  PORT=10000
  CHECK_INTERVAL_SEC=120
  DB_PATH="data.db"
  MAX_SEEN_PER_USER=3000
"""

import os
import sys
import time
import json
import threading
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import requests
except Exception as e:
    print("ERROR: 'requests' package is required. Add it to requirements.txt (requests).", file=sys.stderr)
    raise

# -------------------- Config --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "10000"))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "120"))
DB_PATH = os.getenv("DB_PATH", "data.db")
MAX_SEEN_PER_USER = int(os.getenv("MAX_SEEN_PER_USER", "3000"))

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# -------------------- DB --------------------
_db_lock = threading.Lock()

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def db_init(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            user_id INTEGER NOT NULL,
            kw TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, kw)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            user_id INTEGER NOT NULL,
            kw TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, kw, link)
        )
    """)
    conn.commit()

def add_keyword(conn, user_id: int, kw: str) -> bool:
    kw = kw.strip()
    if not kw:
        return False
    with _db_lock:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO keywords(user_id, kw, created_at) VALUES(?,?,?)",
                (user_id, kw, int(time.time()))
            )
            conn.commit()
            return True
        except Exception:
            return False

def remove_keyword(conn, user_id: int, kw: str) -> bool:
    kw = kw.strip()
    if not kw:
        return False
    with _db_lock:
        cur = conn.execute("DELETE FROM keywords WHERE user_id=? AND kw=?", (user_id, kw))
        conn.commit()
        return cur.rowcount > 0

def list_keywords(conn, user_id: int):
    with _db_lock:
        cur = conn.execute("SELECT kw FROM keywords WHERE user_id=? ORDER BY created_at ASC", (user_id,))
        return [r[0] for r in cur.fetchall()]

def list_all_keywords(conn):
    with _db_lock:
        cur = conn.execute("SELECT user_id, kw FROM keywords")
        return cur.fetchall()

def seen_has(conn, user_id: int, kw: str, link: str) -> bool:
    with _db_lock:
        cur = conn.execute("SELECT 1 FROM seen WHERE user_id=? AND kw=? AND link=? LIMIT 1", (user_id, kw, link))
        return cur.fetchone() is not None

def seen_add(conn, user_id: int, kw: str, link: str):
    with _db_lock:
        conn.execute(
            "INSERT OR IGNORE INTO seen(user_id, kw, link, created_at) VALUES(?,?,?,?)",
            (user_id, kw, link, int(time.time()))
        )
        # simple cleanup per user (keep newest MAX_SEEN_PER_USER)
        cur = conn.execute("SELECT COUNT(*) FROM seen WHERE user_id=?", (user_id,))
        count = int(cur.fetchone()[0])
        if count > MAX_SEEN_PER_USER:
            # delete oldest 10% to reduce churn
            delete_n = max(1, MAX_SEEN_PER_USER // 10)
            conn.execute("""
                DELETE FROM seen
                WHERE rowid IN (
                    SELECT rowid FROM seen
                    WHERE user_id=?
                    ORDER BY created_at ASC
                    LIMIT ?
                )
            """, (user_id, delete_n))
        conn.commit()

# -------------------- Telegram API helpers --------------------
def tg_request(method: str, payload: dict | None = None, timeout: int = 25):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")
    url = f"{API_BASE}/{method}"
    try:
        r = requests.post(url, json=(payload or {}), timeout=timeout)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"ok": False, "description": f"request failed: {e}"}

def tg_send(chat_id: int, text: str):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    _, data = tg_request("sendMessage", payload, timeout=25)
    return data

def tg_delete_webhook():
    # important: if webhook exists, polling can conflict
    _, data = tg_request("deleteWebhook", {"drop_pending_updates": True}, timeout=25)
    return data

# -------------------- RSS --------------------
def google_news_rss_url(query: str) -> str:
    # HL/GL/CE can be customized; keeping it stable
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

def fetch_rss_entries(keyword: str, limit: int = 20):
    url = google_news_rss_url(keyword)
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    # Parse XML (RSS)
    root = ET.fromstring(r.text)
    channel = root.find("channel")
    if channel is None:
        return []
    items = channel.findall("item") or []
    out = []
    for it in items[:limit]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title or link:
            out.append({"title": title, "link": link})
    return out

# -------------------- Command handling --------------------
HELP_TEXT = (
    "سلام 👋\n"
    "دستورها:\n"
    "/add keyword\n"
    "/remove keyword\n"
    "/list\n\n"
    "مثال:\n"
    "/add bitcoin\n"
)

def parse_command(text: str):
    text = (text or "").strip()
    if not text.startswith("/"):
        return None, None
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg

def handle_message(conn, chat_id: int, text: str):
    cmd, arg = parse_command(text)
    if not cmd:
        # ignore normal messages (or you can treat them as /add)
        return

    if cmd in ("/start", "/help"):
        tg_send(chat_id, HELP_TEXT)
        return

    if cmd == "/add":
        kw = arg
        if not kw:
            tg_send(chat_id, "⚠️ مثال: /add bitcoin")
            return
        ok = add_keyword(conn, chat_id, kw)
        if ok:
            tg_send(chat_id, f"✅ Added: {kw}")
        else:
            tg_send(chat_id, "⚠️ نتونستم اضافه کنم (شاید تکراریه).")
        return

    if cmd == "/remove":
        kw = arg
        if not kw:
            tg_send(chat_id, "⚠️ مثال: /remove bitcoin")
            return
        ok = remove_keyword(conn, chat_id, kw)
        if ok:
            tg_send(chat_id, f"✅ Removed: {kw}")
        else:
            tg_send(chat_id, f"ℹ️ پیدا نشد: {kw}")
        return

    if cmd == "/list":
        kws = list_keywords(conn, chat_id)
        if not kws:
            tg_send(chat_id, "📭 لیست خالی است.")
        else:
            tg_send(chat_id, "📌 Monitoring:\n- " + "\n- ".join(kws))
        return

    tg_send(chat_id, "❓ دستور ناشناس. /help")

# -------------------- Polling loop --------------------
def polling_loop(conn):
    """
    Single polling loop. If you run 2 instances of this bot with the same token,
    Telegram will throw "Conflict: terminated by other getUpdates request".
    """
    offset = 0
    while True:
        payload = {"timeout": 50, "offset": offset, "allowed_updates": ["message"]}
        status, data = tg_request("getUpdates", payload, timeout=60)

        if not data.get("ok"):
            desc = (data.get("description") or "")
            print("getUpdates error:", desc)
            # Conflict means another instance is polling: wait and retry
            if "Conflict" in desc or "terminated by other getUpdates" in desc:
                time.sleep(8)
            else:
                time.sleep(3)
            continue

        updates = data.get("result") or []
        for upd in updates:
            offset = max(offset, int(upd.get("update_id", 0)) + 1)
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = msg.get("text")
            if isinstance(chat_id, int) and isinstance(text, str):
                handle_message(conn, chat_id, text)

# -------------------- Monitor loop --------------------
def monitor_loop(conn):
    while True:
        pairs = list_all_keywords(conn)  # [(user_id, kw), ...]
        for user_id, kw in pairs:
            try:
                entries = fetch_rss_entries(kw, limit=20)
                for e in entries:
                    link = (e.get("link") or "").strip()
                    title = (e.get("title") or "").strip() or "No title"
                    if not link:
                        continue
                    if seen_has(conn, user_id, kw, link):
                        continue
                    seen_add(conn, user_id, kw, link)
                    tg_send(user_id, f"🔎 {kw}\n{title}\n{link}")
            except Exception as e:
                # don't crash the loop on one keyword
                print(f"monitor error for kw='{kw}':", e)
        time.sleep(CHECK_INTERVAL_SEC)

# -------------------- Render keepalive HTTP server --------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        # silence logs
        return

def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"HTTP server listening on port {PORT}")
    server.serve_forever()

# -------------------- Main --------------------
def main():
    if not BOT_TOKEN:
        raise SystemExit("Missing BOT_TOKEN environment variable")

    conn = db_connect()
    db_init(conn)

    # IMPORTANT: delete webhook to avoid polling conflicts with webhook mode
    print("Deleting webhook (if any)...")
    print(tg_delete_webhook())

    # Start HTTP server thread (Render healthcheck)
    threading.Thread(target=start_http_server, daemon=True).start()

    # Start monitor loop thread
    threading.Thread(target=monitor_loop, args=(conn,), daemon=True).start()

    # Start polling in main thread
    print("Starting Telegram polling...")
    polling_loop(conn)

if __name__ == "__main__":
    main()
