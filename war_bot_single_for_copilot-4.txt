# -*- coding: utf-8 -*-
"""
ربات جنگ استراتژیک - نسخه تک‌فایلی (مخصوص Pydroid / موبایل)
همه‌چیز (تنظیمات + دیتابیس + کیبورد + هندلرها) توی همین یک فایله
تا هیچ مشکل import بین فایل‌ها پیش نیاد.

نصب پکیج‌های لازم (از داخل Pydroid > Pip):
    aiogram
    aiosqlite
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ==================== تنظیمات ====================
# اول از environment variable میخونه (برای سرور)، اگه نبود از مقدار پیش‌فرض (برای اجرای محلی/Pydroid)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
DB_PATH = "war_bot.db"

START_GOLD = 100
START_COINS = 500
START_ENERGY = 100
MAX_ENERGY = 100
ENERGY_REGEN_MINUTES = 5

START_HP = 100
MAX_HP = 100
XP_BASE_PER_LEVEL = 100

COUNTRIES = {
    "iran":    {"name": "🇮🇷 ایران",   "bonus": "🛢 تولید نفت +۱۰٪"},
    "usa":     {"name": "🇺🇸 آمریکا",  "bonus": "⚔️ قدرت نظامی +۱۰٪"},
    "russia":  {"name": "🇷🇺 روسیه",   "bonus": "⛏ تولید آهن +۱۰٪"},
    "china":   {"name": "🇨🇳 چین",     "bonus": "👥 جمعیت +۱۰٪"},
    "germany": {"name": "🇩🇪 آلمان",   "bonus": "🔬 سرعت تحقیقات +۱۰٪"},
}

DAILY_MISSIONS = [
    {"id": "login",            "title": "✅ ورود روزانه",         "goal": 1, "reward_coins": 50,  "reward_xp": 20},
    {"id": "battle_bot",       "title": "🤖 ۳ نبرد با ربات",       "goal": 3, "reward_coins": 100, "reward_xp": 40},
    {"id": "collect_resource", "title": "⛏ ۱ بار استخراج منابع",  "goal": 1, "reward_coins": 30,  "reward_xp": 15},
]


# ==================== دیتابیس ====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                country TEXT DEFAULT NULL,
                gold INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 0,
                max_energy INTEGER DEFAULT 100,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                xp_needed INTEGER DEFAULT 100,
                last_energy_update TEXT,
                created_at TEXT,
                is_registered INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_missions (
                user_id INTEGER,
                mission_id TEXT,
                progress INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                mission_date TEXT,
                PRIMARY KEY (user_id, mission_id, mission_date)
            )
        """)
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, username: str, full_name: str):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users
            (user_id, username, full_name, gold, coins, energy, max_energy,
             hp, max_hp, level, xp, xp_needed, last_energy_update, created_at, is_registered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, 0)
        """, (
            user_id, username, full_name, START_GOLD, START_COINS,
            START_ENERGY, MAX_ENERGY, START_HP, MAX_HP,
            XP_BASE_PER_LEVEL, now, now,
        ))
        await db.commit()


async def set_country(user_id: int, country_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET country = ?, is_registered = 1 WHERE user_id = ?",
            (country_code, user_id),
        )
        await db.commit()


async def update_fields(user_id: int, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {keys} WHERE user_id = ?", values)
        await db.commit()


async def add_coins(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def regen_energy(user_id: int):
    user = await get_user(user_id)
    if not user:
        return None

    if user["energy"] >= user["max_energy"]:
        await update_fields(user_id, last_energy_update=datetime.utcnow().isoformat())
        return user

    last_update = datetime.fromisoformat(user["last_energy_update"])
    elapsed_minutes = (datetime.utcnow() - last_update).total_seconds() / 60
    regen_amount = int(elapsed_minutes // ENERGY_REGEN_MINUTES)

    if regen_amount > 0:
        new_energy = min(user["max_energy"], user["energy"] + regen_amount)
        used_minutes = regen_amount * ENERGY_REGEN_MINUTES
        new_last_update = last_update + timedelta(minutes=used_minutes)
        await update_fields(
            user_id,
            energy=new_energy,
            last_energy_update=new_last_update.isoformat(),
        )
        user["energy"] = new_energy

    return user


async def add_xp(user_id: int, amount: int):
    user = await get_user(user_id)
    if not user:
        return []

    xp = user["xp"] + amount
    level = user["level"]
    xp_needed = user["xp_needed"]
    levels_gained = []

    while xp >= xp_needed:
        xp -= xp_needed
        level += 1
        xp_needed = level * XP_BASE_PER_LEVEL
        levels_gained.append(level)

    await update_fields(user_id, xp=xp, level=level, xp_needed=xp_needed)
    return levels_gained


def _today():
    return datetime.utcnow().strftime("%Y-%m-%d")


async def ensure_daily_missions(user_id: int):
    today = _today()
    async with aiosqlite.connect(DB_PATH) as db:
        for mission in DAILY_MISSIONS:
            await db.execute("""
                INSERT OR IGNORE INTO daily_missions (user_id, mission_id, progress, completed, claimed, mission_date)
                VALUES (?, ?, 0, 0, 0, ?)
            """, (user_id, mission["id"], today))
        await db.commit()


async def get_daily_missions(user_id: int):
    await ensure_daily_missions(user_id)
    today = _today()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM daily_missions WHERE user_id = ? AND mission_date = ?",
            (user_id, today),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_mission_progress(user_id: int, mission_id: str, amount: int = 1):
    today = _today()
    mission_def = next((m for m in DAILY_MISSIONS if m["id"] == mission_id), None)
    if not mission_def:
        return

    await ensure_daily_missions(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM daily_missions WHERE user_id = ? AND mission_id = ? AND mission_date = ?",
            (user_id, mission_id, today),
        )
        row = await cur.fetchone()
        if not row or row["completed"]:
            return

        new_progress = min(mission_def["goal"], row["progress"] + amount)
        completed = 1 if new_progress >= mission_def["goal"] else 0
        await db.execute("""
            UPDATE daily_missions SET progress = ?, completed = ?
            WHERE user_id = ? AND mission_id = ? AND mission_date = ?
        """, (new_progress, completed, user_id, mission_id, today))
        await db.commit()


async def claim_mission_reward(user_id: int, mission_id: str):
    today = _today()
    mission_def = next((m for m in DAILY_MISSIONS if m["id"] == mission_id), None)
    if not mission_def:
        return False, None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM daily_missions WHERE user_id = ? AND mission_id = ? AND mission_date = ?",
            (user_id, mission_id, today),
        )
        row = await cur.fetchone()
        if not row or not row["completed"] or row["claimed"]:
            return False, mission_def

        await db.execute("""
            UPDATE daily_missions SET claimed = 1
            WHERE user_id = ? AND mission_id = ? AND mission_date = ?
        """, (user_id, mission_id, today))
        await db.commit()

    await add_coins(user_id, mission_def["reward_coins"])
    await add_xp(user_id, mission_def["reward_xp"])
    return True, mission_def


# ==================== کیبوردها ====================
def country_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, data in COUNTRIES.items():
        builder.button(text=data["name"], callback_data=f"country:{code}")
    builder.adjust(2)
    return builder.as_markup()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 پروفایل من", callback_data="menu:profile")
    builder.button(text="🎯 ماموریت‌های روزانه", callback_data="menu:missions")
    builder.button(text="⚔️ نبرد", callback_data="menu:battle")
    builder.button(text="🏛 ارتش و ساختمان‌ها", callback_data="menu:army")
    builder.button(text="🌍 اتحاد", callback_data="menu:alliance")
    builder.button(text="🏪 بازار و فروشگاه", callback_data="menu:market")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ بازگشت", callback_data="menu:main")
    return builder.as_markup()


def missions_kb(missions: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in missions:
        mission_def = next((d for d in DAILY_MISSIONS if d["id"] == m["mission_id"]), None)
        if not mission_def:
            continue
        if m["claimed"]:
            label = f"✅ {mission_def['title']} (دریافت‌شده)"
        elif m["completed"]:
            label = f"🎁 {mission_def['title']} - دریافت جایزه"
        else:
            label = f"⏳ {mission_def['title']} ({m['progress']}/{mission_def['goal']})"
        builder.button(text=label, callback_data=f"claim_mission:{m['mission_id']}")
    builder.button(text="⬅️ بازگشت", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# ==================== هندلرها ====================
router = Router()

COMING_SOON = {
    "menu:battle": "⚔️ سیستم نبرد به‌زودی اضافه میشه!",
    "menu:army": "🏛 سیستم ارتش و ساختمان‌سازی به‌زودی اضافه میشه!",
    "menu:alliance": "🌍 سیستم اتحاد به‌زودی اضافه میشه!",
    "menu:market": "🏪 بازار و فروشگاه به‌زودی اضافه میشه!",
}


def _progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int(length * current / total) if total else 0
    return "▰" * filled + "▱" * (length - filled)


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)

    if not user:
        await create_user(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            full_name=message.from_user.full_name,
        )
        user = await get_user(message.from_user.id)

    if not user["is_registered"]:
        await message.answer(
            "🎮 <b>به بازی خوش اومدی، فرمانده!</b>\n\n"
            "قبل از شروع باید کشور یا جناح خودت رو انتخاب کنی.\n"
            "هر کشور یه بونوس مخصوص خودش داره 👇",
            reply_markup=country_selection_kb(),
        )
        return

    await update_mission_progress(message.from_user.id, "login", 1)

    await message.answer(
        f"👋 خوش اومدی {message.from_user.full_name}!\n\nاز منوی زیر بخش موردنظرت رو انتخاب کن:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("country:"))
async def choose_country(callback: CallbackQuery):
    country_code = callback.data.split(":")[1]
    if country_code not in COUNTRIES:
        await callback.answer("کشور نامعتبره!", show_alert=True)
        return

    await set_country(callback.from_user.id, country_code)
    await update_mission_progress(callback.from_user.id, "login", 1)

    country = COUNTRIES[country_code]
    await callback.message.edit_text(
        f"✅ کشور <b>{country['name']}</b> با موفقیت انتخاب شد!\n"
        f"🎁 بونوس این کشور: {country['bonus']}\n\n"
        f"حالا می‌تونی بازی رو شروع کنی 👇",
    )
    await callback.message.answer("منوی اصلی:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def show_profile(callback: CallbackQuery):
    user = await regen_energy(callback.from_user.id)
    if not user:
        await callback.answer("اول باید ثبت‌نام کنی، دستور /start رو بزن.", show_alert=True)
        return

    country = COUNTRIES.get(user["country"], {}).get("name", "نامشخص")
    xp_bar = _progress_bar(user["xp"], user["xp_needed"])
    hp_bar = _progress_bar(user["hp"], user["max_hp"])
    energy_bar = _progress_bar(user["energy"], user["max_energy"])

    text = (
        f"👤 <b>پروفایل {callback.from_user.full_name}</b>\n"
        f"🌍 کشور: {country}\n\n"
        f"📊 لول: <b>{user['level']}</b>\n"
        f"✨ XP: {user['xp']}/{user['xp_needed']}\n{xp_bar}\n\n"
        f"❤️ جان: {user['hp']}/{user['max_hp']}\n{hp_bar}\n\n"
        f"⚡️ انرژی: {user['energy']}/{user['max_energy']}\n{energy_bar}\n\n"
        f"💰 سکه: {user['coins']}\n"
        f"🪙 طلا: {user['gold']}"
    )

    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "منوی اصلی — بخش موردنظرت رو انتخاب کن:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:missions")
async def show_missions(callback: CallbackQuery):
    missions = await get_daily_missions(callback.from_user.id)
    await callback.message.edit_text(
        "🎯 <b>ماموریت‌های امروز</b>\n\nهر ماموریت رو کامل کن و جایزه‌شو بگیر:",
        reply_markup=missions_kb(missions),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("claim_mission:"))
async def claim_mission(callback: CallbackQuery):
    mission_id = callback.data.split(":")[1]
    success, mission_def = await claim_mission_reward(callback.from_user.id, mission_id)

    if success:
        await callback.answer(
            f"🎉 جایزه دریافت شد: {mission_def['reward_coins']} سکه + {mission_def['reward_xp']} XP",
            show_alert=True,
        )
    else:
        await callback.answer("این ماموریت هنوز کامل نشده یا قبلاً جایزه‌شو گرفتی.", show_alert=True)

    missions = await get_daily_missions(callback.from_user.id)
    await callback.message.edit_text(
        "🎯 <b>ماموریت‌های امروز</b>\n\nهر ماموریت رو کامل کن و جایزه‌شو بگیر:",
        reply_markup=missions_kb(missions),
    )


@router.callback_query(F.data.in_(COMING_SOON.keys()))
async def coming_soon(callback: CallbackQuery):
    await callback.answer(COMING_SOON[callback.data], show_alert=True)


# ==================== اجرا ====================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
