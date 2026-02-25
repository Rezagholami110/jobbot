# main.py
# FastAPI + aiogram v3 webhook entrypoint.
#
# Environment variables:
#   BOT_TOKEN   - Telegram bot token (required)
#   WEBHOOK_URL - Optional. If set, app will try to set webhook to WEBHOOK_URL + '/telegram' on startup.
#
# Render start command:
#   uvicorn main:app --host 0.0.0.0 --port $PORT

from __future__ import annotations

import os
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

import db
from jobs import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("care_worke_bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    # Render will still start the service, but bot won't work until token is set.
    logger.warning("BOT_TOKEN is not set. Set it in your hosting environment variables.")

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()
dp.include_router(router)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await db.init_db()

    # Optional: auto-set webhook (useful on some platforms)
    webhook_base = os.environ.get("WEBHOOK_URL", "").strip()
    if bot and webhook_base:
        url = webhook_base.rstrip("/") + "/telegram"
        try:
            await bot.set_webhook(url, allowed_updates=["message", "callback_query"])
            logger.info("Webhook set to %s", url)
        except Exception:
            logger.exception("Failed to set webhook automatically")


@app.get("/")
async def health():
    return {"status": "ok"}


@app.get("/telegram")
async def telegram_health():
    return {"ok": True}


@app.post("/telegram")
async def telegram_webhook(request: Request):
    if not bot:
        return {"ok": False, "error": "BOT_TOKEN not set"}

    payload = await request.json()
    update = Update.model_validate(payload)

    # Feed update to aiogram dispatcher
    await dp.feed_update(bot, update)
    return {"ok": True}
