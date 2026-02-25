# jobs.py
# aiogram v3 handlers + menus + language selection.
# Data is per-user and stored in SQLite via db.py.

from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import db

router = Router()

LANGS = ["fa", "ru", "en", "ka"]

TEXTS = {
    "fa": {
        "choose_lang": "زبان را انتخاب کن:",
        "menu_title": "منوی اصلی:",
        "btn_add": "➕ افزودن کلمه",
        "btn_list": "📋 لیست کلمات",
        "btn_del_one": "🗑 حذف یک کلمه",
        "btn_del_all": "🧹 حذف همه کلمات",
        "btn_settings": "⚙️ تنظیمات",
        "prompt_add": "کلمه را بفرست (یا /start برای برگشت به منو):",
        "prompt_del_one": "کلمه‌ای که می‌خوای حذف کنی را دقیقاً بفرست:",
        "saved": "✅ ذخیره شد.",
        "exists": "ℹ️ این کلمه قبلاً ذخیره شده بود.",
        "deleted_one": "✅ حذف شد.",
        "not_found": "❌ پیدا نشد.",
        "deleted_all": "✅ همه کلماتت حذف شد. تعداد: {n}",
        "empty": "لیستت خالیه.",
        "list_header": "کلمات تو (حداکثر 200 تا):",
        "confirm_del_all": "مطمئنی می‌خوای همه کلماتت پاک بشه؟",
        "yes": "✅ بله",
        "no": "❌ خیر",
        "lang_set": "✅ زبان تنظیم شد.",
    },
    "en": {
        "choose_lang": "Choose a language:",
        "menu_title": "Main menu:",
        "btn_add": "➕ Add word",
        "btn_list": "📋 List words",
        "btn_del_one": "🗑 Delete one",
        "btn_del_all": "🧹 Delete all",
        "btn_settings": "⚙️ Settings",
        "prompt_add": "Send the word (or /start to return to menu):",
        "prompt_del_one": "Send the exact word to delete:",
        "saved": "✅ Saved.",
        "exists": "ℹ️ This word is already saved.",
        "deleted_one": "✅ Deleted.",
        "not_found": "❌ Not found.",
        "deleted_all": "✅ All your words were deleted. Count: {n}",
        "empty": "Your list is empty.",
        "list_header": "Your words (up to 200):",
        "confirm_del_all": "Are you sure you want to delete ALL your words?",
        "yes": "✅ Yes",
        "no": "❌ No",
        "lang_set": "✅ Language updated.",
    },
    "ru": {
        "choose_lang": "Выберите язык:",
        "menu_title": "Главное меню:",
        "btn_add": "➕ Добавить слово",
        "btn_list": "📋 Список слов",
        "btn_del_one": "🗑 Удалить одно",
        "btn_del_all": "🧹 Удалить всё",
        "btn_settings": "⚙️ Настройки",
        "prompt_add": "Отправьте слово (или /start чтобы вернуться в меню):",
        "prompt_del_one": "Отправьте точное слово для удаления:",
        "saved": "✅ Сохранено.",
        "exists": "ℹ️ Это слово уже сохранено.",
        "deleted_one": "✅ Удалено.",
        "not_found": "❌ Не найдено.",
        "deleted_all": "✅ Все ваши слова удалены. Кол-во: {n}",
        "empty": "Список пуст.",
        "list_header": "Ваши слова (до 200):",
        "confirm_del_all": "Точно удалить ВСЕ ваши слова?",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "lang_set": "✅ Язык обновлён.",
    },
    "ka": {
        "choose_lang": "აირჩიე ენა:",
        "menu_title": "მთავარი მენიუ:",
        "btn_add": "➕ სიტყვის დამატება",
        "btn_list": "📋 სიტყვების სია",
        "btn_del_one": "🗑 ერთის წაშლა",
        "btn_del_all": "🧹 ყველაფრის წაშლა",
        "btn_settings": "⚙️ პარამეტრები",
        "prompt_add": "გამოგზავნე სიტყვა (ან /start მენიუში დასაბრუნებლად):",
        "prompt_del_one": "ზუსტად გამოაგზავნე წასაშლელი სიტყვა:",
        "saved": "✅ შენახულია.",
        "exists": "ℹ️ ეს სიტყვა უკვე შენახულია.",
        "deleted_one": "✅ წაშლილია.",
        "not_found": "❌ ვერ მოიძებნა.",
        "deleted_all": "✅ ყველა შენი სიტყვა წაიშალა. რაოდენობა: {n}",
        "empty": "სია ცარიელია.",
        "list_header": "შენი სიტყვები (მაქს 200):",
        "confirm_del_all": "დარწმუნებული ხარ, რომ გინდა ყველა სიტყვის წაშლა?",
        "yes": "✅ კი",
        "no": "❌ არა",
        "lang_set": "✅ ენა განახლდა.",
    },
}

STATE_ADD = "ADD_WORD"
STATE_DEL_ONE = "DEL_ONE"


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["en"]).get(key, key)


def main_menu_kb(lang: str):
    kb = ReplyKeyboardBuilder()
    kb.button(text=t(lang, "btn_add"))
    kb.button(text=t(lang, "btn_list"))
    kb.button(text=t(lang, "btn_del_one"))
    kb.button(text=t(lang, "btn_del_all"))
    kb.button(text=t(lang, "btn_settings"))
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="فارسی", callback_data="lang:fa")
    kb.button(text="Русский", callback_data="lang:ru")
    kb.button(text="English", callback_data="lang:en")
    kb.button(text="ქართული", callback_data="lang:ka")
    kb.adjust(2, 2)
    return kb.as_markup()


def confirm_del_all_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "yes"), callback_data="delall:yes")
    kb.button(text=t(lang, "no"), callback_data="delall:no")
    kb.adjust(2)
    return kb.as_markup()


# Reverse map to detect which menu button was pressed across languages
ACTION_BY_TEXT = {}
for action_key, text_key in [
    ("ADD", "btn_add"),
    ("LIST", "btn_list"),
    ("DEL_ONE", "btn_del_one"),
    ("DEL_ALL", "btn_del_all"),
    ("SETTINGS", "btn_settings"),
]:
    for lg in LANGS:
        ACTION_BY_TEXT[t(lg, text_key)] = action_key


@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    await db.ensure_user(user_id)
    lang = await db.get_lang(user_id)

    # Always show language chooser first-time (when user row just created it's 'fa' already).
    # We use a small trick: if user_state is empty and no words exist, still ask language.
    # You can change this behavior later.
    await message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def set_language(cb: CallbackQuery):
    user_id = cb.from_user.id
    lang = cb.data.split(":", 1)[1].strip()
    if lang not in LANGS:
        lang = "en"
    await db.set_lang(user_id, lang)
    await db.clear_state(user_id)

    await cb.answer(t(lang, "lang_set"))
    await cb.message.answer(t(lang, "menu_title"), reply_markup=main_menu_kb(lang))


@router.message(F.text)
async def menu_and_states(message: Message):
    user_id = message.from_user.id
    await db.ensure_user(user_id)
    lang = await db.get_lang(user_id)

    # If user is in a state, process it first
    state = await db.get_state(user_id)

    if state == STATE_ADD:
        ok = await db.add_word(user_id, message.text)
        await db.clear_state(user_id)
        await message.answer(t(lang, "saved") if ok else t(lang, "exists"), reply_markup=main_menu_kb(lang))
        return

    if state == STATE_DEL_ONE:
        n = await db.delete_word(user_id, message.text)
        await db.clear_state(user_id)
        await message.answer(t(lang, "deleted_one") if n else t(lang, "not_found"), reply_markup=main_menu_kb(lang))
        return

    # Otherwise interpret menu action
    action = ACTION_BY_TEXT.get(message.text.strip())
    if not action:
        # Ignore random text in idle mode, but keep helpful menu
        await message.answer(t(lang, "menu_title"), reply_markup=main_menu_kb(lang))
        return

    if action == "ADD":
        await db.set_state(user_id, STATE_ADD)
        await message.answer(t(lang, "prompt_add"))
        return

    if action == "LIST":
        words = await db.list_words(user_id, limit=200)
        if not words:
            await message.answer(t(lang, "empty"), reply_markup=main_menu_kb(lang))
            return
        lines = "\n".join([f"{i+1}. {w}" for i, w in enumerate(words)])
        await message.answer(f"{t(lang, 'list_header')}\n\n{lines}", reply_markup=main_menu_kb(lang))
        return

    if action == "DEL_ONE":
        await db.set_state(user_id, STATE_DEL_ONE)
        await message.answer(t(lang, "prompt_del_one"))
        return

    if action == "DEL_ALL":
        await message.answer(t(lang, "confirm_del_all"), reply_markup=confirm_del_all_kb(lang))
        return

    if action == "SETTINGS":
        await message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())
        return


@router.callback_query(F.data.startswith("delall:"))
async def del_all(cb: CallbackQuery):
    user_id = cb.from_user.id
    lang = await db.get_lang(user_id)
    choice = cb.data.split(":", 1)[1].strip()

    if choice == "yes":
        n = await db.delete_all_words(user_id)
        await cb.answer("OK")
        await cb.message.answer(t(lang, "deleted_all").format(n=n), reply_markup=main_menu_kb(lang))
    else:
        await cb.answer("OK")
        await cb.message.answer(t(lang, "menu_title"), reply_markup=main_menu_kb(lang))
