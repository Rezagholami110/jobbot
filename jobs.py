import feedparser
import requests
import time

BOT_TOKEN = "8693197814:AAFTatkKU5IGDUb5p-0RYPnNtqklOZ9WzVE"
CHAT_ID = "138974947"

FEEDS = [
    "https://www.indeed.co.uk/rss?q=care+worker+visa+sponsorship&l=London"
]

def send(text):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

print("Bot started...")
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_http():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('', port), Handler)
    server.serve_forever()

threading.Thread(target=run_http).start()
while True:
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            send(entry.title + "\n" + entry.link)
            time.sleep(1)


    time.sleep(1800)

