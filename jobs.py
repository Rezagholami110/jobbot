def gdelt_search(query: str, max_records: int = 15):
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


def check_keywords(seen: set):
    kws = load_json(KEYWORDS_FILE, [])
    for kw in kws:
        try:
            articles = gdelt_search(kw, max_records=15)
        except Exception:
            continue

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
            # ذخیره آخرین‌ها (برای جلوگیری از بزرگ شدن فایل)
            save_json(SEEN_FILE, sorted(list(seen))[-8000:])
        except Exception as e:
            tg_send(f"⚠️ Error: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)

# ----------------- HTTP server for Render -----------------
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

# ----------------- Main -----------------
def main():
    if not BOT_TOKEN or not CHAT_ID or not ADMIN_ID_STR:
        raise SystemExit("Missing BOT_TOKEN / CHAT_ID / ADMIN_ID in environment variables")

    # HTTP thread (برای اینکه Render بگه سرویس زنده است)
    threading.Thread(target=run_http, daemon=True).start()

    # مانیتور در یک thread جدا
    threading.Thread(target=monitor_loop, daemon=True).start()

    # Telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("list", list_cmd))

    # Run polling (blocking)
    app.run_polling()

if name == "main":
    main()
