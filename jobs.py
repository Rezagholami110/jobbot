import os
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import feedparser
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
ADMIN_ID_STR = os.getenv("ADMIN_ID", "").strip()

JOB_FEEDS = [
"[https://www.indeed.co.uk/rss?q=care+worker+visa+sponsorship&l=London](https://www.indeed.co.uk/rss?q=care+worker+visa+sponsorship&l=London)",
]

KEYWORDS_FILE = "keywords.json"
SEEN_FILE = "seen_links.json"

CHECK_INTERVAL_SECONDS = 1800

def tg_send(text: str):
if not BOT_TOKEN or not CHAT_ID:
return
url = f"[https://api.telegram.org/bot{BOT_TOKEN}/sendMessage](https://api.telegram.org/bot{BOT_TOKEN}/sendMessage)"
try:
requests.post(
url,
json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
timeout=25
)
except Exception:
pass

def load_json(path, default):
try:
with open(path, "r", encoding="utf-8") as f:
return json.load(f)
except Exception:
return default

def save_json(path, data):
try:
with open(path, "w", encoding="utf-8") as f:
json.dump(data, f, ensure_ascii=False, indent=2)
except Exception:
pass

def is_admin(update: Update) -> bool:
try:
return update.effective_user and update.effective_user.id == int(ADMIN_ID_STR)
except Exception:
return False

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
return
await update.message.reply_text(
"✅ Online.\n"
"Commands:\n"
"/add <word>\n"
"/remove <word>\n"
"/list\n"
"/ping"
)

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
return
await update.message.reply_text("✅ Pong. Bot is alive.")

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
return
if not context.args:
await update.message.reply_text("مثال: /add sushi")
return

```
word = " ".join(context.args).strip()
kws = load_json(KEYWORDS_FILE, [])
if word not in kws:
    kws.append(word)
    save_json(KEYWORDS_FILE, kws)

await update.message.reply_text(f"✅ Added: {word}")
```

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
return
if not context.args:
await update.message.reply_text("مثال: /remove sushi")
return

```
word = " ".join(context.args).strip()
kws = load_json(KEYWORDS_FILE, [])
kws = [k for k in kws if k != word]
save_json(KEYWORDS_FILE, kws)

await update.message.reply_text(f"🗑 Removed: {word}")
```

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not is_admin(update):
return

```
kws = load_json(KEYWORDS_FILE, [])
if not kws:
    await update.message.reply_text("لیست خالیه. مثلا: /add sushi")
    return

await update.message.reply_text("📌 Monitoring:\n- " + "\n- ".join(kws))
```

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
endpoint = "[https://api.gdeltproject.org/api/v2/doc/doc](https://api.gdeltproject.org/api/v2/doc/doc)"
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

def check_keywords(seen: set):
kws = load_json(KEYWORDS_FILE, [])
for kw in kws:
try:
articles = gdelt_search(kw, max_records=15)
except Exception:
continue

```
    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "Result")
        key = f"KW::{kw}::{url}"
        if not url or key in seen:
            continue
        tg_send(f"🔎 {kw}\n{title}\n{url}")
        seen.add(key)
        time.sleep(1)
```

def monitor_loop():
tg_send("✅ Bot started (jobs + keywords).")

```
seen_list = load_json(SEEN_FILE, [])
seen = set(seen_list if isinstance(seen_list, list) else [])

while True:
    try:
        check_jobs(seen)
        check_keywords(seen)
        save_json(SEEN_FILE, sorted(list(seen))[-8000:])
    except Exception as e:
        tg_send(f"⚠️ Error: {e}")
    time.sleep(CHECK_INTERVAL_SECONDS)
```

class Handler(BaseHTTPRequestHandler):
def do_GET(self):
self.send_response(200)
self.end_headers()
self.wfile.write(b"Bot is running")

```
def do_HEAD(self):
    self.send_response(200)
    self.end_headers()
```

def run_http():
port = int(os.environ.get("PORT", "10000"))
HTTPServer(("", port), Handler).serve_forever()

def main():
if not BOT_TOKEN or not CHAT_ID or not ADMIN_ID_STR:
raise SystemExit("Missing BOT_TOKEN / CHAT_ID / ADMIN_ID in environment variables")

```
threading.Thread(target=run_http, daemon=True).start()
threading.Thread(target=monitor_loop, daemon=True).start()

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start_cmd))
app.add_handler(CommandHandler("ping", ping_cmd))
app.add_handler(CommandHandler("add", add_cmd))
app.add_handler(CommandHandler("remove", remove_cmd))
app.add_handler(CommandHandler("list", list_cmd))

app.run_polling()
```

if **name** == "**main**":
main()

