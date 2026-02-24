# -*- coding: utf-8 -*-
import os
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import feedparser
from telegram.ext import Updater, CommandHandler

# --------- ENV (در Render تنظیم می‌کنی) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN"8693197814:AAFTatkKU5IGDUb5p-0RYPnNtqklOZ9WzVE"").strip()
CHAT_ID = os.getenv("CHAT_ID"138974947"").strip()           # جایی که پیام‌ها ارسال می‌شود (پی‌وی/گروه/کانال)
ADMIN_ID = int(os.getenv("ADMIN_ID"138974947"0").strip())   # فقط خودت
# -------------------------------------------------

# RSS های کاری
JOB_FEEDS = [
    "https://www.indeed.co.uk/rss?q=care+worker+visa+sponsorship&l=London",
]

# Keyword monitoring (با GDELT: رایگان)
KEYWORDS_FILE = "keywords.json"
SEEN_FILE = "seen_links.json"

CHECK_INTERVAL_SECONDS = 30 * 60   # هر 30 دقیقه (می‌تونی 10*60 کنی)

def tg_send(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=25)

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID

# ---------- Commands ----------
def start_cmd(update, context):
    if not is_admin(update):
        return
    update.message.reply_text("✅ Online.\nCommands:\n/add <word>\n/remove <word>\n/list")

def add_cmd(update, context):
    if not is_admin(update):
        return
    if not context.args:
        update.message.reply_text("مثال: /add sushi")
        return
    word = " ".join(context.args).strip()
    kws = load_json(KEYWORDS_FILE, [])
    if word not in kws:
        kws.append(word)
        save_json(KEYWORDS_FILE, kws)
    update.message.reply_text(f"✅ Added: {word}")

def remove_cmd(update, context):
    if not is_admin(update):
        return
    if not context.args:
        update.message.reply_text("مثال: /remove sushi")
        return
    word = " ".join(context.args).strip()
    kws = load_json(KEYWORDS_FILE, [])
    kws = [k for k in kws if k != word]
    save_json(KEYWORDS_FILE, kws)
    update.message.reply_text(f"🗑 Removed: {word}")

def list_cmd(update, context):
    if not is_admin(update):
        return
    kws = load_json(KEYWORDS_FILE, [])
    if not kws:
        update.message.reply_text("لیست خالیه. مثلا: /add sushi")
        return
    update.message.reply_text("📌 Monitoring:\n- " + "\n- ".join(kws))

# ---------- Monitors ----------
def check_jobs(seen):
    for feed_url in JOB_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:25]:
            link = entry.get("link", "")
            title = entry.get("title", "Job")
            key = f"JOB::{link}"
            if not link or key in seen:
                continue
            tg_send(f"🧾 Job\n{title}\n{link}")
            seen.add(key)
            time.sleep(1)

def gdelt_search(query, max_records=15):
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "DateDesc"
    }
    r = requests.get(endpoint, params=params, timeout=25)
    r.raise_for_status()
    return r.json().get("articles", []) or []

def check_keywords(seen):
    kws = load_json(KEYWORDS_FILE, [])
    for kw in kws:
        articles = gdelt_search(kw, max_records=15)
        for a in articles:
            url = a.get("url", "")
            title = a.get("title", "Result")
            key = f"KW::{kw}::{url}"
            if not url or key in seen:
                continue
            tg_send(f"🔎 {kw}\n{title}\n{url}")
            seen.add(key)
            time.sleep(1)

def monitor_loop():
    tg_send("✅ Bot started (jobs + keywords).")
    seen_list = load_json(SEEN_FILE, [])
    seen = set(seen_list if isinstance(seen_list, list) else [])

    while True:
        try:
            check_jobs(seen)
            check_keywords(seen)
            # ذخیره seen
            save_json(SEEN_FILE, sorted(list(seen))[-8000:])
        except Exception as e:
            # خطا را برای خودت بفرست (اختیاری)
            try:
                tg_send(f"⚠️ Error: {e}")
            except:
                pass
        time.sleep(CHECK_INTERVAL_SECONDS)

# ---------- HTTP server for Render ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_http():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("", port), Handler).serve_forever()

def main():
    if not BOT_TOKEN or not CHAT_ID or not ADMIN_ID:
        raise SystemExit("Missing BOT_TOKEN / CHAT_ID / ADMIN_ID in environment variables")

    # HTTP thread
    threading.Thread(target=run_http, daemon=True).start()

    # Telegram command listener (polling)
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("add", add_cmd))
    dp.add_handler(CommandHandler("remove", remove_cmd))
    dp.add_handler(CommandHandler("list", list_cmd))
    updater.start_polling()

    # monitor loop
    monitor_loop()

if __name__ == "__main__":
    main()
