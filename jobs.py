import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import feedparser
import requests

from db import add_keyword, remove_keyword, list_keywords, list_all_keywords
from telegram.ext import Updater, CommandHandler
# -------------------- ENV (Render -> Settings -> Environment) --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID_DEFAULT = os.getenv("CHAT_ID", "").strip()  # اختیاری
ADMIN_ID_STR = os.getenv("ADMIN_ID", "0").strip()

# -------- Render HTTP keepalive --------
PORT = int(os.getenv("PORT", "10000"))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return

def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()
# -------- end keepalive --------
def must_int(x: str, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

ADMIN_ID = must_int(ADMIN_ID_STR, 0)

# -------------------- SETTINGS --------------------
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "120"))  # هر 2 دقیقه
SEEN_MAX = int(os.getenv("SEEN_MAX", "2000"))  # سقف حافظه لینک‌های دیده‌شده

# -------------------- In-memory seen set --------------------
seen_lock = threading.Lock()
seen = set()  # کلیدهای دیده‌شده (در RAM)

# -------------------- Telegram send (raw HTTP) --------------------
def tg_send(text: str, chat_id=None):
    if not BOT_TOKEN:
        return
    cid = chat_id or CHAT_ID_DEFAULT
    if not cid:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": cid,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=25,
        )
    except Exception:
        pass

# -------------------- RSS fetch --------------------
def fetch_google_news_rss(keyword: str):
    # Google News RSS
    url = f"https://news.google.com/rss/search?q={keyword}"
    feed = feedparser.parse(url)
    return feed.entries[:5]

def run_check_once():
    pairs = list_all_keywords()  # [(user_id, keyword), ...]
    for user_id, kw in pairs:
        try:
            entries = fetch_google_news_rss(kw)
            for entry in entries:
                link = (entry.get("link") or "").strip()
                title = (entry.get("title") or "No title").strip()

                if not link:
                    continue

                key = f"kw:{user_id}:{kw}:{link}"

                with seen_lock:
                    if key in seen:
                        continue
                    seen.add(key)
                    # کنترل اندازه seen
                    if len(seen) > SEEN_MAX:
                        # حذف تعدادی (ساده و سریع)
                        for _ in range(SEEN_MAX // 5):
                            try:
                                seen.pop()
                            except KeyError:
                                break

                tg_send(f"🔎 {kw}\n{title}\n{link}", chat_id=user_id)

        except Exception as e:
            tg_send(f"⚠️ Error for '{kw}': {e}", chat_id=user_id)

def monitor_loop():
    tg_send("✅ Bot started (jobs + keywords).", chat_id=CHAT_ID_DEFAULT or ADMIN_ID or None)
    while True:
        run_check_once()
        time.sleep(CHECK_INTERVAL_SEC)

# -------------------- HTTP server for Render healthcheck --------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

def run_http():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

# -------------------- Telegram bot handlers (supports v13 and v20+) --------------------
def start_text(user_id: int):
    tg_send(
        "سلام 👋\n"
        "دستورها:\n"
        "/add keyword\n"
        "/remove keyword\n"
        "/list\n",
        chat_id=user_id,
    )

def parse_arg(text: str):
    # "/add sushi" -> "sushi"
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()

#v13
from telegram.ext import Updater, CommandHandler
def start_cmd(update, context):
            uid = update.effective_chat.id
            start_text(uid)

        def add_cmd(update, context):
            uid = update.effective_chat.id
            kw = parse_arg(update.message.text)
            if not kw:
                tg_send("⚠️ مثال: /add bitcoin", chat_id=uid)
                return
            add_keyword(uid, kw)
            tg_send(f"✅ Added: {kw}", chat_id=uid)

        def remove_cmd(update, context):
            uid = update.effective_chat.id
            kw = parse_arg(update.message.text)
            if not kw:
                tg_send("⚠️ مثال: /remove bitcoin", chat_id=uid)
                return
            remove_keyword(uid, kw)
            tg_send(f"✅ Removed: {kw}", chat_id=uid)

        def list_cmd(update, context):
            uid = update.effective_chat.id
            kws = list_keywords(uid)
            if not kws:
                tg_send("📭 لیست خالی است.", chat_id=uid)
                return
            tg_send("📌 Monitoring:\n- " + "\n- ".join(kws), chat_id=uid)
            
def main():
    threading.Thread(target=start_http_server, daemon=True).start()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("add", add_cmd))
    dp.add_handler(CommandHandler("remove", remove_cmd))
    dp.add_handler(CommandHandler("list", list_cmd))
    
    try:
        updater.start_polling(drop_pending_updates=True)
        updater.idle()
    except Exception as e:
        print("Polling error:", e)
        time.sleep(5)


if __name__ == "__main__":
    main()














