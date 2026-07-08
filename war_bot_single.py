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
# روی Railway حتماً یه Volume بساز (مثلاً با Mount Path = /data) و متغیر محیطی DB_PATH رو
# روی مسیر داخل همون Volume بذار (مثلاً /data/war_bot.db). وگرنه هر ری‌دیپلوی/ری‌استارت
# دیتابیس از صفر میشه چون فایل‌سیستم کانتینر پایدار نیست.
DB_PATH = os.environ.get("DB_PATH", "war_bot.db")

START_GOLD = 100
START_COINS = 500
START_ENERGY = 100
MAX_ENERGY = 100
ENERGY_REGEN_MINUTES = 5

START_HP = 100
MAX_HP = 100
XP_BASE_PER_LEVEL = 100

COUNTRIES = {
    "iran":         {"name": "🇮🇷 ایران",        "bonus": "🪙 تولید طلا +۱۲٪",      "bonus_type": "gold_pct",     "bonus_value": 0.12},
    "usa":          {"name": "🇺🇸 آمریکا",       "bonus": "⚔️ قدرت نظامی +۱۲٪",     "bonus_type": "military_pct", "bonus_value": 0.12},
    "russia":       {"name": "🇷🇺 روسیه",        "bonus": "💰 تولید سکه +۱۲٪",      "bonus_type": "coins_pct",    "bonus_value": 0.12},
    "china":        {"name": "🇨🇳 چین",          "bonus": "💰 تولید سکه +۱۳٪",      "bonus_type": "coins_pct",    "bonus_value": 0.13},
    "germany":      {"name": "🇩🇪 آلمان",        "bonus": "✨ کسب XP +۱۲٪",         "bonus_type": "xp_pct",       "bonus_value": 0.12},
    "france":       {"name": "🇫🇷 فرانسه",       "bonus": "⚔️ قدرت نظامی +۱۰٪",     "bonus_type": "military_pct", "bonus_value": 0.10},
    "uk":           {"name": "🇬🇧 بریتانیا",     "bonus": "🪙 تولید طلا +۱۰٪",      "bonus_type": "gold_pct",     "bonus_value": 0.10},
    "japan":        {"name": "🇯🇵 ژاپن",         "bonus": "✨ کسب XP +۱۳٪",         "bonus_type": "xp_pct",       "bonus_value": 0.13},
    "south_korea":  {"name": "🇰🇷 کره‌جنوبی",     "bonus": "✨ کسب XP +۱۰٪",         "bonus_type": "xp_pct",       "bonus_value": 0.10},
    "north_korea":  {"name": "🇰🇵 کره‌شمالی",     "bonus": "⚔️ قدرت نظامی +۱۵٪",     "bonus_type": "military_pct", "bonus_value": 0.15},
    "india":        {"name": "🇮🇳 هند",          "bonus": "💰 تولید سکه +۱۲٪",      "bonus_type": "coins_pct",    "bonus_value": 0.12},
    "pakistan":     {"name": "🇵🇰 پاکستان",      "bonus": "⚔️ قدرت نظامی +۱۰٪",     "bonus_type": "military_pct", "bonus_value": 0.10},
    "israel":       {"name": "🇮🇱 اسرائیل",      "bonus": "⚔️ قدرت نظامی +۱۴٪",     "bonus_type": "military_pct", "bonus_value": 0.14},
    "saudi_arabia": {"name": "🇸🇦 عربستان",      "bonus": "🪙 تولید طلا +۱۵٪",      "bonus_type": "gold_pct",     "bonus_value": 0.15},
    "turkey":       {"name": "🇹🇷 ترکیه",        "bonus": "⚔️ قدرت نظامی +۱۰٪",     "bonus_type": "military_pct", "bonus_value": 0.10},
    "egypt":        {"name": "🇪🇬 مصر",          "bonus": "💰 تولید سکه +۱۰٪",      "bonus_type": "coins_pct",    "bonus_value": 0.10},
    "uae":          {"name": "🇦🇪 امارات",       "bonus": "🪙 تولید طلا +۱۳٪",      "bonus_type": "gold_pct",     "bonus_value": 0.13},
    "brazil":       {"name": "🇧🇷 برزیل",        "bonus": "💰 تولید سکه +۱۱٪",      "bonus_type": "coins_pct",    "bonus_value": 0.11},
    "canada":       {"name": "🇨🇦 کانادا",       "bonus": "🪙 تولید طلا +۱۰٪",      "bonus_type": "gold_pct",     "bonus_value": 0.10},
    "australia":    {"name": "🇦🇺 استرالیا",     "bonus": "🪙 تولید طلا +۱۱٪",      "bonus_type": "gold_pct",     "bonus_value": 0.11},
    "italy":        {"name": "🇮🇹 ایتالیا",      "bonus": "✨ کسب XP +۹٪",          "bonus_type": "xp_pct",       "bonus_value": 0.09},
    "spain":        {"name": "🇪🇸 اسپانیا",      "bonus": "💰 تولید سکه +۹٪",       "bonus_type": "coins_pct",    "bonus_value": 0.09},
    "poland":       {"name": "🇵🇱 لهستان",       "bonus": "⚔️ قدرت نظامی +۹٪",      "bonus_type": "military_pct", "bonus_value": 0.09},
    "ukraine":      {"name": "🇺🇦 اوکراین",      "bonus": "⚔️ قدرت نظامی +۱۱٪",     "bonus_type": "military_pct", "bonus_value": 0.11},
    "sweden":       {"name": "🇸🇪 سوئد",         "bonus": "✨ کسب XP +۱۰٪",         "bonus_type": "xp_pct",       "bonus_value": 0.10},
    "switzerland":  {"name": "🇨🇭 سوئیس",        "bonus": "🪙 تولید طلا +۱۲٪",      "bonus_type": "gold_pct",     "bonus_value": 0.12},
    "indonesia":    {"name": "🇮🇩 اندونزی",      "bonus": "💰 تولید سکه +۱۰٪",      "bonus_type": "coins_pct",    "bonus_value": 0.10},
    "mexico":       {"name": "🇲🇽 مکزیک",        "bonus": "💰 تولید سکه +۹٪",       "bonus_type": "coins_pct",    "bonus_value": 0.09},
    "south_africa": {"name": "🇿🇦 آفریقای‌جنوبی", "bonus": "🪙 تولید طلا +۱۲٪",      "bonus_type": "gold_pct",     "bonus_value": 0.12},
    "vietnam":      {"name": "🇻🇳 ویتنام",       "bonus": "💰 تولید سکه +۹٪",       "bonus_type": "coins_pct",    "bonus_value": 0.09},
}

DAILY_MISSIONS = [
    {"id": "login",            "title": "✅ ورود روزانه",         "goal": 1, "reward_coins": 50,  "reward_xp": 20},
    {"id": "battle_bot",       "title": "🤖 ۳ نبرد با ربات",       "goal": 3, "reward_coins": 100, "reward_xp": 40},
    {"id": "collect_resource", "title": "⛏ ۱ بار استخراج منابع",  "goal": 1, "reward_coins": 30,  "reward_xp": 15},
]

# ---- ساختمان‌ها و اقتصاد بازی ----
# هر ساختمان: هزینه ساخت/ارتقا با نرخ رشد نمایی زیاد میشه، تولیدش هم هر سطح زیاد میشه.
# currency=None یعنی ساختمان تولیدکننده منبع نیست (مثل انبار که فقط ظرفیت ذخیره رو زیاد میکنه).
BUILDINGS = {
    "farm": {
        "name": "🌾 مزرعه",
        "currency": "coins",       # منبعی که تولید میکنه
        "resource": "coins",       # منبعی که برای ارتقا خرج میشه
        "base_cost": 100,
        "cost_growth": 1.55,
        "base_production": 15,    # سکه در ساعت، در سطح ۱
        "production_growth": 1.25,
        "max_level": 20,
    },
    "mine": {
        "name": "⛏ معدن طلا",
        "currency": "gold",
        "resource": "coins",
        "base_cost": 250,
        "cost_growth": 1.6,
        "base_production": 5,     # طلا در ساعت، در سطح ۱
        "production_growth": 1.22,
        "max_level": 20,
    },
    "warehouse": {
        "name": "🏬 انبار",
        "currency": None,          # چیزی تولید نمی‌کنه، فقط سقف زمانِ انباشتِ تولید رو بالا می‌بره
        "resource": "coins",
        "base_cost": 150,
        "cost_growth": 1.5,
        "max_level": 15,
    },
    "barracks": {
        "name": "🎖 پادگان",
        "currency": None,          # تولیدکننده نیست، سطحش سقف نیروی نظامی و رده‌های واحد رو باز می‌کنه
        "resource": "coins",
        "base_cost": 300,
        "cost_growth": 1.65,
        "max_level": 10,
    },
}
BUILDING_ORDER = ["farm", "mine", "warehouse", "barracks"]

WAREHOUSE_BASE_HOURS = 12       # ظرفیت انباشت تولید بدون هیچ انبار (سطح ۰)
WAREHOUSE_HOURS_PER_LEVEL = 2   # هر سطح انبار چقدر به ظرفیت اضافه میکنه

ARMY_BASE_CAPACITY = 20         # سقف تعداد کل نیروی نظامی بدون پادگان
ARMY_CAPACITY_PER_BARRACKS_LEVEL = 15  # هر سطح پادگان چقدر به سقف نیرو اضافه میکنه

# ---- واحدهای نظامی ----
# unlock_level: حداقل سطح پادگان لازم برای دسترسی به این واحد
UNITS = {
    "infantry":         {"name": "🪖 پیاده‌نظام",        "unlock_level": 0,  "cost_coins": 50,    "cost_gold": 0,    "power": 5,    "upkeep": 1},
    "sniper":           {"name": "🎯 تک‌تیرانداز",       "unlock_level": 1,  "cost_coins": 150,   "cost_gold": 0,    "power": 12,   "upkeep": 2},
    "apc":              {"name": "🚙 نفربر زرهی",        "unlock_level": 2,  "cost_coins": 400,   "cost_gold": 5,    "power": 30,   "upkeep": 4},
    "tank":             {"name": "🛡 تانک",              "unlock_level": 3,  "cost_coins": 900,   "cost_gold": 15,   "power": 70,   "upkeep": 8},
    "artillery":        {"name": "💥 توپخانه",           "unlock_level": 4,  "cost_coins": 1500,  "cost_gold": 30,   "power": 120,  "upkeep": 12},
    "helicopter":       {"name": "🚁 بالگرد جنگی",       "unlock_level": 5,  "cost_coins": 2500,  "cost_gold": 60,   "power": 200,  "upkeep": 20},
    "fighter_jet":      {"name": "🛩 جنگنده",            "unlock_level": 6,  "cost_coins": 5000,  "cost_gold": 150,  "power": 400,  "upkeep": 40},
    "warship":          {"name": "🚢 ناوشکن",            "unlock_level": 7,  "cost_coins": 9000,  "cost_gold": 300,  "power": 700,  "upkeep": 70},
    "submarine":        {"name": "🛥 زیردریایی",         "unlock_level": 8,  "cost_coins": 15000, "cost_gold": 500,  "power": 1200, "upkeep": 120},
    "missile_launcher": {"name": "🚀 سامانه موشکی",      "unlock_level": 10, "cost_coins": 30000, "cost_gold": 1000, "power": 2500, "upkeep": 250},
}
UNIT_ORDER = [
    "infantry", "sniper", "apc", "tank", "artillery",
    "helicopter", "fighter_jet", "warship", "submarine", "missile_launcher",
]


def building_upgrade_cost(building_id: str, current_level: int):
    """هزینه ارتقا از current_level به سطح بعدی. اگه به سقف رسیده باشه None برمیگردونه."""
    b = BUILDINGS[building_id]
    if current_level >= b["max_level"]:
        return None
    return int(b["base_cost"] * (b["cost_growth"] ** current_level))


def building_production_per_hour(building_id: str, level: int) -> int:
    b = BUILDINGS[building_id]
    if level <= 0 or b.get("currency") is None:
        return 0
    return int(b["base_production"] * (b["production_growth"] ** (level - 1)))


def building_storage_cap_hours(warehouse_level: int) -> int:
    return WAREHOUSE_BASE_HOURS + warehouse_level * WAREHOUSE_HOURS_PER_LEVEL


def army_capacity(barracks_level: int) -> int:
    return ARMY_BASE_CAPACITY + barracks_level * ARMY_CAPACITY_PER_BARRACKS_LEVEL


def country_bonus(country_code: str, bonus_type: str) -> float:
    """درصد بونوس یک کشور برای یک نوع مشخص (military_pct/coins_pct/gold_pct/xp_pct). صفر یعنی بونوسی نداره."""
    country = COUNTRIES.get(country_code)
    if not country or country.get("bonus_type") != bonus_type:
        return 0.0
    return country.get("bonus_value", 0.0)


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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_buildings (
                user_id INTEGER,
                building_id TEXT,
                level INTEGER DEFAULT 0,
                last_collect TEXT,
                PRIMARY KEY (user_id, building_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_army (
                user_id INTEGER,
                unit_id TEXT,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, unit_id)
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN military_power INTEGER DEFAULT 0")
        except Exception:
            pass  # ستون از قبل وجود داره (روی دیتابیس‌های قدیمی‌تر)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_upkeep_update TEXT")
        except Exception:
            pass
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_power ON users(military_power DESC)")
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

    bonus = country_bonus(user.get("country"), "xp_pct")
    amount = int(amount * (1 + bonus))

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


# ==================== ساختمان‌ها و اقتصاد ====================
async def ensure_buildings(user_id: int):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        for b_id in BUILDING_ORDER:
            await db.execute("""
                INSERT OR IGNORE INTO user_buildings (user_id, building_id, level, last_collect)
                VALUES (?, ?, 0, ?)
            """, (user_id, b_id, now))
        await db.commit()


async def get_user_buildings(user_id: int) -> dict:
    await ensure_buildings(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_buildings WHERE user_id = ?", (user_id,))
        rows = await cur.fetchall()
        return {r["building_id"]: dict(r) for r in rows}


async def upgrade_building(user_id: int, building_id: str):
    """تلاش برای ارتقای یک ساختمان. خروجی: (suc * FROM daily_missions WHERE user_id = ? AND mission_id = ? AND mission_date = ?",
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


# ==================== ساختمان‌ها و اقتصاد ====================
async def ensure_buildings(user_id: int):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        for b_id in BUILDING_ORDER:
            await db.execute("""
                INSERT OR IGNORE INTO user_buildings (user_id, building_id, level, last_collect)
                VALUES (?, ?, 0, ?)
            """, (user_id, b_id, now))
        await db.commit()


async def get_user_buildings(user_id: int) -> dict:
    await ensure_buildings(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_buildings WHERE user_id = ?", (user_id,))
        rows = await cur.fetchall()
        return {r["building_id"]: dict(r) for r in rows}


async def upgrade_building(user_id: int, building_id: str):
    """تلاش برای ارتقای یک ساختمان. خروجی: (success: bool, message: str)"""
    if building_id not in BUILDINGS:
        return False, "ساختمان نامعتبره."

    user = await get_user(user_id)
    if not user:
        return False, "اول باید ثبت‌نام کنی، دستور /start رو بزن."

    buildings = await get_user_buildings(user_id)
    current_level = buildings.get(building_id, {}).get("level", 0)

    cost = building_upgrade_cost(building_id, current_level)
    if cost is None:
        return False, f"{BUILDINGS[building_id]['name']} به حداکثر سطح رسیده! 🏆"

    resource = BUILDINGS[building_id]["resource"]
    balance = user[resource]
    if balance < cost:
        resource_label = "سکه" if resource == "coins" else "طلا"
        return False, f"{resource_label} کافی نداری! نیاز: {cost} — موجودی: {balance}"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {resource} = {resource} - ? WHERE user_id = ?",
            (cost, user_id),
        )
        await db.execute(
            "UPDATE user_buildings SET level = level + 1 WHERE user_id = ? AND building_id = ?",
            (user_id, building_id),
        )
        await db.commit()

    return True, f"✅ {BUILDINGS[building_id]['name']} به سطح {current_level + 1} ارتقا یافت!"


async def collect_building_income(user_id: int) -> dict:
    """درآمد انباشته‌ی همه‌ی ساختمان‌های تولیدکننده رو برداشت می‌کنه. خروجی: {"coins": x, "gold": y}"""
    buildings = await get_user_buildings(user_id)
    now = datetime.utcnow()
    warehouse_level = buildings.get("warehouse", {}).get("level", 0)
    cap_hours = building_storage_cap_hours(warehouse_level)

    earned = {"coins": 0, "gold": 0}
    async with aiosqlite.connect(DB_PATH) as db:
        for b_id, row in buildings.items():
            b = BUILDINGS[b_id]
            currency = b.get("currency")
            level = row["level"]
            if not currency or level <= 0:
                continue

            last_collect = datetime.fromisoformat(row["last_collect"])
            elapsed_hours = (now - last_collect).total_seconds() / 3600
            elapsed_hours = min(elapsed_hours, cap_hours)  # جلوگیری از انباشت بی‌نهایت
            if elapsed_hours <= 0:
                continue

            per_hour = building_production_per_hour(b_id, level)
            amount = int(per_hour * elapsed_hours)
            if amount > 0:
                earned[currency] += amount

            await db.execute(
                "UPDATE user_buildings SET last_collect = ? WHERE user_id = ? AND building_id = ?",
                (now.isoformat(), user_id, b_id),
            )
        await db.commit()

    if earned["coins"] > 0:
        await add_coins(user_id, earned["coins"])
    if earned["gold"] > 0:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (earned["gold"], user_id))
            await db.commit()

    if earned["coins"] > 0 or earned["gold"] > 0:
        await update_mission_progress(user_id, "collect_resource", 1)

    return earned


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


def buildings_kb(buildings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b_id in BUILDING_ORDER:
        b = BUILDINGS[b_id]
        level = buildings.get(b_id, {}).get("level", 0)
        cost = building_upgrade_cost(b_id, level)
        if cost is None:
            label = f"{b['name']} (سطح {level} — حداکثر)"
        else:
            resource_icon = "💰" if b["resource"] == "coins" else "🪙"
            label = f"{b['name']} (سطح {level}) ⬆️ {cost}{resource_icon}"
        builder.button(text=label, callback_data=f"build:upgrade:{b_id}")
    builder.button(text="💰 برداشت درآمد", callback_data="build:collect")
    builder.button(text="⬅️ بازگشت", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def buildings_text(buildings: dict) -> str:
    lines = ["🏛 <b>ساختمان‌های اقتصادی</b>\n"]
    for b_id in BUILDING_ORDER:
        b = BUILDINGS[b_id]
        level = buildings.get(b_id, {}).get("level", 0)
        if b.get("currency"):
            per_hour = building_production_per_hour(b_id, level)
            icon = "💰" if b["currency"] == "coins" else "🪙"
            lines.append(f"{b['name']} — سطح {level} — تولید: {per_hour}{icon}/ساعت")
        else:
            cap_hours = building_storage_cap_hours(level)
            lines.append(f"{b['name']} — سطح {level} — ظرفیت انباشت تولید: {cap_hours} ساعت")
    lines.append(
        "\nهر ساختمان رو ارتقا بده تا تولیدت بیشتر بشه.\n"
        "⚠️ یادت نره سر وقت درآمدت رو برداشت کنی، چون تولید بیشتر از ظرفیت انبار هدر میره!"
    )
    return "\n".join(lines)


# ==================== هندلرها ====================
router = Router()

COMING_SOON = {
    "menu:battle": "⚔️ سیستم نبرد به‌زودی اضافه میشه!",
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


@router.callback_query(F.data == "menu:army")
async def show_buildings(callback: CallbackQuery):
    buildings = await get_user_buildings(callback.from_user.id)
    await callback.message.edit_text(
        buildings_text(buildings),
        reply_markup=buildings_kb(buildings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("build:upgrade:"))
async def handle_upgrade_building(callback: CallbackQuery):
    building_id = callback.data.split(":")[2]
    success, msg = await upgrade_building(callback.from_user.id, building_id)
    await callback.answer(msg, show_alert=True)

    buildings = await get_user_buildings(callback.from_user.id)
    await callback.message.edit_text(
        buildings_text(buildings),
        reply_markup=buildings_kb(buildings),
    )


@router.callback_query(F.data == "build:collect")
async def handle_collect_income(callback: CallbackQuery):
    earned = await collect_building_income(callback.from_user.id)

    if earned["coins"] == 0 and earned["gold"] == 0:
        await callback.answer("چیزی برای برداشت نیست، صبر کن ساختمان‌هات تولید کنن.", show_alert=True)
    else:
        parts = []
        if earned["coins"] > 0:
            parts.append(f"{earned['coins']} سکه")
        if earned["gold"] > 0:
            parts.append(f"{earned['gold']} طلا")
        await callback.answer(f"🎉 برداشت شد: {' و '.join(parts)}", show_alert=True)

    buildings = await get_user_buildings(callback.from_user.id)
    await callback.message.edit_text(
        buildings_text(buildings),
        reply_markup=buildings_kb(buildings),
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
