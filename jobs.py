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

while True:
    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            send(entry.title + "\n" + entry.link)
            time.sleep(1)

    time.sleep(1800)