import os
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import feedparser
from db import add_keyword, list_keywords, remove_keyword, list_all_keywords
from telegram.ext import Updater, CommandHandler

# ---------------- ENV (Render -> Settings -> Environment) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()          # جایی که پیام‌ها ارسال می‌شود
ADMIN_ID_STR = os.getenv("ADMIN_ID", "").strip()    # فقط خودت (عدد)
# -----------------------------------------------------------------------

# ---------------- CONFIG ----------------
JOB_FEEDS = [
    "https://www.indeed.co.uk/rss?q=care+worker+visa+sponsorship&l=London",
]

KEYWORDS_FILE = "keywords.json"     # ذخیره کلمات مانیتور
SEEN_FILE = "seen_links.json"       # جلوگیری از تکرار ارسال لینک‌ها

CHECK_INTERVAL_SECONDS = 30 * 60    # هر ۳۰ دقیقه
# ---------------------------------------


# ---------------- Utilities ----------------
def must_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except Exception:
        return default


ADMIN_ID = must_int(ADMIN_ID_STR, 0)


def tg_send(text: str):
    """
    ارسال پیام به تلگرام (بدون نیاز به python-telegram-bot برای ارسال)
    """
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=25
    )


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_admin(update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


# ---------------- Telegram Commands ----------------
def start_cmd(update, context):
    if not is_admin(update):
        return
    update.message.reply_text(
        "✅ Online.\n\n"
        "Commands:\n"
        "/add <word>\n"
        "/remove <word>\n"
        "/list\n"
        "/ping"
    )


def ping_cmd(update, context):
    if not is_admin(update):
        return
    update.message.reply_text("🏓 Pong! Bot is alive.")


def add_cmd(update, context):
    if not is_admin(update):
        return

    if not context.args:
        update.message.reply_text("Usage: /add <word>")
        return

    word = context.args[0]
    user_id = update.effective_user.id

    add_keyword(user_id, word)
    update.message.reply_text(f"Added: {word}")

def list_cmd(update, context):
    if not is_admin(update):
        return

    user_id = update.effective_user.id
    keywords = list_keywords(user_id)

    if not keywords:
        update.message.reply_text("Empty")
    else:
        update.message.reply_text("\n".join(keywords))


def remove_cmd(update, context):
    if not is_admin(update):
        return

    if not context.args:
        update.message.reply_text("Usage: /remove <word>")
        return

    word = context.args[0]
    user_id = update.effective_user.id

    remove_keyword(user_id, word)
    update.message.reply_text(f"Removed: {word}")
    if not is_admin(update):
        return
    update.message.reply_text("🏓 Pong! Bot is alive.")


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


# ---------------- Monitors ----------------
def check_jobs(seen: set):
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


def gdelt_search(query: str, max_records: int = 15):
    """
    GDELT Docs API (رایگان) - خروجی اخبار/وب
    """
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "DateDesc",
    }
    r = requests.get(endpoint, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    return data.get("articles", []) or []


def check_keywords(seen: set):
 pairs = list_all_keywords()

    for user_id, kw in pairs:
        url = f"https://news.google.com/rss/search?q={kw}"
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            link = entry.get("link", "")
            title = entry.get("title", "No title")

            key = f"kw:{user_id}:{kw}:{link}"
            if not link or key in seen:
                continue

            tg_send(f"🔎 {kw}\n{title}\n{link}", chat_id=user_id)
            seen.add(key)

def monitor_loop():
    tg_send("✅ Bot started (jobs + keywords).")

    seen_list = load_json(SEEN_FILE, [])
    if isinstance(seen_list, list):
        seen = set(seen_list)
    else:
        seen = set()

    while True:
        try:
            check_jobs(seen)
            check_keywords(seen)

            # ذخیره seen (برای جلوگیری از بزرگ شدن فایل)
            save_json(SEEN_FILE, sorted(list(seen))[-8000:])
            time.sleep(300)  # 5 minutes delay
        except Exception as e:
            # خطا را برای خودت بفرست (اختیاری)
            try:
                tg_send(f"⚠️ Error: {e}")
            except Exception:
                pass

        time.sleep(CHECK_INTERVAL_SECONDS)


# ---------------- HTTP Server for Render (Port Binding) ----------------
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


# ---------------- Main ----------------
def main():
    if not BOT_TOKEN or not CHAT_ID or ADMIN_ID == 0:
        raise SystemExit("Missing BOT_TOKEN / CHAT_ID / ADMIN_ID in environment variables")

    # HTTP thread (برای اینکه Render بگه سرویس پورت باز کرده)
    threading.Thread(target=run_http, daemon=True).start()

    # Telegram command listener (polling)
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("ping", ping_cmd))
    dp.add_handler(CommandHandler("add", add_cmd))
    dp.add_handler(CommandHandler("remove", remove_cmd))
    dp.add_handler(CommandHandler("list", list_cmd))

    updater.start_polling(drop_pending_updates=True)


updater.idle()

if __name__ == "__main__":
    main()





