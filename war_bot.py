# -*- coding: utf-8 -*-
"""
ربات جنگ استراتژیک - نسخه پیشرفته (تک‌فایلی، مخصوص Pydroid / موبایل / سرور)
همه‌چیز (تنظیمات + دیتابیس + کیبورد + هندلرها) توی همین یک فایله
تا هیچ مشکل import بین فایل‌ها پیش نیاد.

ویژگی‌های این نسخه نسبت به نسخه قبل:
    - تفکیک نیروی نظامی به ۴ دسته: زمینی / هوایی / دریایی / استراتژیک
    - سیستم نبرد کامل (PvE با ربات + PvP تصادفی با بازیکن‌های دیگه)
    - UI بازطراحی‌شده با جداکننده، اعداد فرمت‌شده و منوهای چندسطحی
    - لایه دیتابیس بهینه‌شده: یک کانکشن مشترک به‌جای باز/بسته‌ی مکرر + قفل برای جلوگیری از ریس‌کاندیشن
    - قفل هر کاربر برای جلوگیری از دبل‌تپ روی خرید/ارتقا/نبرد (جلوگیری از خرج شدن دوباره‌ی موجودی)
    - هندل کامل خطاها؛ هیچ خطایی کرش کل ربات رو باعث نمیشه

نصب پکیج‌های لازم (از داخل Pydroid > Pip یا pip معمولی):
    aiogram
    aiosqlite
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger("war_bot")


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
HP_REGEN_MINUTES = 8  # هر ۸ دقیقه ۱ جان برمیگرده

XP_BASE_PER_LEVEL = 100

# ---- تنظیمات نبرد ----
BATTLE_ENERGY_COST = 15
BATTLE_MIN_HP = 15
BATTLE_HP_LOSS_MIN_LOSE = 8
BATTLE_HP_LOSS_MAX_LOSE = 20
BATTLE_HP_LOSS_MIN_WIN = 2
BATTLE_HP_LOSS_MAX_WIN = 8

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
    {"id": "battle_win",       "title": "🏆 برد در ۱ نبرد",        "goal": 1, "reward_coins": 80,  "reward_xp": 35},
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

# ---- دسته‌بندی نیروهای نظامی ----
CATEGORIES = {
    "ground":     {"label": "🪖 نیروی زمینی",       "short": "زمینی"},
    "air":        {"label": "🛩 نیروی هوایی",       "short": "هوایی"},
    "naval":      {"label": "⚓ نیروی دریایی",      "short": "دریایی"},
    "strategic":  {"label": "🚀 نیروی استراتژیک",   "short": "استراتژیک"},
}
CATEGORY_ORDER = ["ground", "air", "naval", "strategic"]

# ---- واحدهای نظامی ----
# unlock_level: حداقل سطح پادگان لازم برای دسترسی به این واحد
UNITS = {
    "infantry":         {"name": "🪖 پیاده‌نظام",   "category": "ground",    "unlock_level": 0,  "cost_coins": 50,    "cost_gold": 0,    "power": 5,    "upkeep": 1},
    "sniper":           {"name": "🎯 تک‌تیرانداز",  "category": "ground",    "unlock_level": 1,  "cost_coins": 150,   "cost_gold": 0,    "power": 12,   "upkeep": 2},
    "apc":              {"name": "🚙 نفربر زرهی",   "category": "ground",    "unlock_level": 2,  "cost_coins": 400,   "cost_gold": 5,    "power": 30,   "upkeep": 4},
    "tank":             {"name": "🛡 تانک",         "category": "ground",    "unlock_level": 3,  "cost_coins": 900,   "cost_gold": 15,   "power": 70,   "upkeep": 8},
    "artillery":        {"name": "💥 توپخانه",      "category": "ground",    "unlock_level": 4,  "cost_coins": 1500,  "cost_gold": 30,   "power": 120,  "upkeep": 12},
    "helicopter":       {"name": "🚁 بالگرد جنگی",  "category": "air",       "unlock_level": 5,  "cost_coins": 2500,  "cost_gold": 60,   "power": 200,  "upkeep": 20},
    "fighter_jet":      {"name": "🛩 جنگنده",       "category": "air",       "unlock_level": 6,  "cost_coins": 5000,  "cost_gold": 150,  "power": 400,  "upkeep": 40},
    "warship":          {"name": "🚢 ناوشکن",       "category": "naval",     "unlock_level": 7,  "cost_coins": 9000,  "cost_gold": 300,  "power": 700,  "upkeep": 70},
    "submarine":        {"name": "🛥 زیردریایی",    "category": "naval",     "unlock_level": 8,  "cost_coins": 15000, "cost_gold": 500,  "power": 1200, "upkeep": 120},
    "missile_launcher": {"name": "🚀 سامانه موشکی", "category": "strategic", "unlock_level": 10, "cost_coins": 30000, "cost_gold": 1000, "power": 2500, "upkeep": 250},
}
UNIT_ORDER = [
    "infantry", "sniper", "apc", "tank", "artillery",
    "helicopter", "fighter_jet", "warship", "submarine", "missile_launcher",
]
UNITS_BY_CATEGORY = {cat: [u for u in UNIT_ORDER if UNITS[u]["category"] == cat] for cat in CATEGORY_ORDER}


def _fmt(n) -> str:
    """فرمت عدد با جداکننده هزارگان برای نمایش تمیزتر در UI."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


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


def country_bonus(country_code, bonus_type: str) -> float:
    """درصد بونوس یک کشور برای یک نوع مشخص (military_pct/coins_pct/gold_pct/xp_pct). صفر یعنی بونوسی نداره."""
    country = COUNTRIES.get(country_code)
    if not country or country.get("bonus_type") != bonus_type:
        return 0.0
    return country.get("bonus_value", 0.0)


def unit_power_breakdown(army: dict) -> dict:
    """قدرت خام (بدون بونوس لول/کشور) هر دسته از نیرو رو حساب می‌کنه."""
    result = {cat: 0 for cat in CATEGORY_ORDER}
    for unit_id, count in army.items():
        if count <= 0 or unit_id not in UNITS:
            continue
        cat = UNITS[unit_id]["category"]
        result[cat] += UNITS[unit_id]["power"] * count
    return result


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ==================== لایه دیتابیس (بهینه‌شده) ====================
# به‌جای باز و بستن یک کانکشن جدید برای هر کوئری (که در نسخه قبل هزینه‌ی زیادی داشت)،
# اینجا یک کانکشن مشترک نگه می‌داریم و دسترسی بهش رو با یک قفل سریالایز می‌کنیم
# تا هیچ‌وقت به مشکل "database is locked" یا تداخل کوئری‌های همزمان برنخوریم.
_db_conn: aiosqlite.Connection = None
_db_lock = asyncio.Lock()

# قفل مخصوص هر کاربر، برای جلوگیری از دبل‌تپ روی خرید/ارتقا/نبرد (جلوگیری از ریس‌کاندیشن مالی)
_user_locks: dict = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


async def get_db() -> aiosqlite.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = await aiosqlite.connect(DB_PATH)
        _db_conn.row_factory = aiosqlite.Row
        await _db_conn.execute("PRAGMA journal_mode=WAL")
        await _db_conn.execute("PRAGMA synchronous=NORMAL")
        await _db_conn.execute("PRAGMA foreign_keys=ON")
        await _db_conn.commit()
    return _db_conn


async def close_db():
    global _db_conn
    if _db_conn is not None:
        await _db_conn.close()
        _db_conn = None


async def db_execute(query: str, params: tuple = (), commit: bool = False):
    db = await get_db()
    async with _db_lock:
        cur = await db.execute(query, params)
        if commit:
            await db.commit()
        return cur


async def db_fetchone(query: str, params: tuple = ()):
    db = await get_db()
    async with _db_lock:
        cur = await db.execute(query, params)
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_fetchall(query: str, params: tuple = ()):
    db = await get_db()
    async with _db_lock:
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def init_db():
    db = await get_db()
    async with _db_lock:
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
                last_hp_update TEXT,
                last_upkeep_update TEXT,
                military_power INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
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
        # مهاجرت ستون‌های جدید برای دیتابیس‌های قدیمی‌تر که این ستون‌ها رو ندارن
        for alter_sql in (
            "ALTER TABLE users ADD COLUMN military_power INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_upkeep_update TEXT",
            "ALTER TABLE users ADD COLUMN last_hp_update TEXT",
            "ALTER TABLE users ADD COLUMN wins INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass  # ستون از قبل وجود داره
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_power ON users(military_power DESC)")
        await db.commit()


async def get_user(user_id: int):
    return await db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))


async def create_user(user_id: int, username: str, full_name: str):
    now = datetime.utcnow().isoformat()
    await db_execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, full_name, gold, coins, energy, max_energy,
         hp, max_hp, level, xp, xp_needed, last_energy_update, last_hp_update,
         last_upkeep_update, wins, losses, created_at, is_registered)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, 0, 0, ?, 0)
    """, (
        user_id, username, full_name, START_GOLD, START_COINS,
        START_ENERGY, MAX_ENERGY, START_HP, MAX_HP,
        XP_BASE_PER_LEVEL, now, now, now, now,
    ), commit=True)


async def set_country(user_id: int, country_code: str):
    await db_execute(
        "UPDATE users SET country = ?, is_registered = 1 WHERE user_id = ?",
        (country_code, user_id), commit=True,
    )


async def update_fields(user_id: int, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    await db_execute(f"UPDATE users SET {keys} WHERE user_id = ?", tuple(values), commit=True)


async def add_coins(user_id: int, amount: int):
    if amount == 0:
        return
    await db_execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id), commit=True)


async def add_gold(user_id: int, amount: int):
    if amount == 0:
        return
    await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (amount, user_id), commit=True)


async def _regen_stat(user_id: int, current_field: str, max_field: str, last_update_field: str, regen_minutes: int):
    """تابع عمومی برای ریجن‌کردن انرژی یا جان با گذشت زمان."""
    user = await get_user(user_id)
    if not user:
        return None

    current = user[current_field]
    maximum = user[max_field]
    if current >= maximum:
        await update_fields(user_id, **{last_update_field: datetime.utcnow().isoformat()})
        return user

    last_raw = user.get(last_update_field) or user.get("created_at") or datetime.utcnow().isoformat()
    try:
        last_update = datetime.fromisoformat(last_raw)
    except ValueError:
        last_update = datetime.utcnow()

    elapsed_minutes = (datetime.utcnow() - last_update).total_seconds() / 60
    regen_amount = int(elapsed_minutes // regen_minutes)

    if regen_amount > 0:
        new_value = min(maximum, current + regen_amount)
        used_minutes = regen_amount * regen_minutes
        new_last_update = last_update + timedelta(minutes=used_minutes)
        await update_fields(user_id, **{current_field: new_value, last_update_field: new_last_update.isoformat()})
        user[current_field] = new_value

    return user


async def regen_energy(user_id: int):
    return await _regen_stat(user_id, "energy", "max_energy", "last_energy_update", ENERGY_REGEN_MINUTES)


async def regen_hp(user_id: int):
    return await _regen_stat(user_id, "hp", "max_hp", "last_hp_update", HP_REGEN_MINUTES)


async def regen_all(user_id: int):
    """هم انرژی هم جان رو آپدیت می‌کنه؛ خروجی آخرین وضعیت کاربره."""
    await regen_energy(user_id)
    return await regen_hp(user_id)


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
    db = await get_db()
    async with _db_lock:
        for mission in DAILY_MISSIONS:
            await db.execute("""
                INSERT OR IGNORE INTO daily_missions (user_id, mission_id, progress, completed, claimed, mission_date)
                VALUES (?, ?, 0, 0, 0, ?)
            """, (user_id, mission["id"], today))
        await db.commit()


async def get_daily_missions(user_id: int):
    await ensure_daily_missions(user_id)
    today = _today()
    return await db_fetchall(
        "SELECT * FROM daily_missions WHERE user_id = ? AND mission_date = ?",
        (user_id, today),
    )


async def update_mission_progress(user_id: int, mission_id: str, amount: int = 1):
    today = _today()
    mission_def = next((m for m in DAILY_MISSIONS if m["id"] == mission_id), None)
    if not mission_def:
        return

    await ensure_daily_missions(user_id)
    row = await db_fetchone(
        "SELECT * FROM daily_missions WHERE user_id = ? AND mission_id = ? AND mission_date = ?",
        (user_id, mission_id, today),
    )
    if not row or row["completed"]:
        return

    new_progress = min(mission_def["goal"], row["progress"] + amount)
    completed = 1 if new_progress >= mission_def["goal"] else 0
    await db_execute("""
        UPDATE daily_missions SET progress = ?, completed = ?
        WHERE user_id = ? AND mission_id = ? AND mission_date = ?
    """, (new_progress, completed, user_id, mission_id, today), commit=True)


async def claim_mission_reward(user_id: int, mission_id: str):
    today = _today()
    mission_def = next((m for m in DAILY_MISSIONS if m["id"] == mission_id), None)
    if not mission_def:
        return False, None

    async with get_user_lock(user_id):
        row = await db_fetchone(
            "SELECT * FROM daily_missions WHERE user_id = ? AND mission_id = ? AND mission_date = ?",
            (user_id, mission_id, today),
        )
        if not row or not row["completed"] or row["claimed"]:
            return False, mission_def

        await db_execute("""
            UPDATE daily_missions SET claimed = 1
            WHERE user_id = ? AND mission_id = ? AND mission_date = ?
        """, (user_id, mission_id, today), commit=True)

        await add_coins(user_id, mission_def["reward_coins"])
        await add_xp(user_id, mission_def["reward_xp"])
    return True, mission_def


# ==================== ساختمان‌ها و اقتصاد ====================
async def ensure_buildings(user_id: int):
    now = datetime.utcnow().isoformat()
    db = await get_db()
    async with _db_lock:
        for b_id in BUILDING_ORDER:
            await db.execute("""
                INSERT OR IGNORE INTO user_buildings (user_id, building_id, level, last_collect)
                VALUES (?, ?, 0, ?)
            """, (user_id, b_id, now))
        await db.commit()


async def get_user_buildings(user_id: int) -> dict:
    await ensure_buildings(user_id)
    rows = await db_fetchall("SELECT * FROM user_buildings WHERE user_id = ?", (user_id,))
    return {r["building_id"]: r for r in rows}


async def upgrade_building(user_id: int, building_id: str):
    """تلاش برای ارتقای یک ساختمان. خروجی: (success: bool, message: str)"""
    if building_id not in BUILDINGS:
        return False, "ساختمان نامعتبره."

    async with get_user_lock(user_id):
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
            return False, f"{resource_label} کافی نداری! نیاز: {_fmt(cost)} — موجودی: {_fmt(balance)}"

        db = await get_db()
        async with _db_lock:
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
    async with get_user_lock(user_id):
        user = await get_user(user_id)
        buildings = await get_user_buildings(user_id)
        now = datetime.utcnow()
        warehouse_level = buildings.get("warehouse", {}).get("level", 0)
        cap_hours = building_storage_cap_hours(warehouse_level)
        country = user.get("country") if user else None
        coins_bonus = country_bonus(country, "coins_pct")
        gold_bonus = country_bonus(country, "gold_pct")

        earned = {"coins": 0, "gold": 0}
        db = await get_db()
        async with _db_lock:
            for b_id, row in buildings.items():
                b = BUILDINGS[b_id]
                currency = b.get("currency")
                level = row["level"]
                if not currency or level <= 0:
                    continue

                try:
                    last_collect = datetime.fromisoformat(row["last_collect"])
                except (ValueError, TypeError):
                    last_collect = now
                elapsed_hours = (now - last_collect).total_seconds() / 3600
                elapsed_hours = min(elapsed_hours, cap_hours)  # جلوگیری از انباشت بی‌نهایت
                if elapsed_hours <= 0:
                    continue

                per_hour = building_production_per_hour(b_id, level)
                bonus = coins_bonus if currency == "coins" else gold_bonus
                amount = int(per_hour * elapsed_hours * (1 + bonus))
                if amount > 0:
                    earned[currency] += amount

                await db.execute(
                    "UPDATE user_buildings SET last_collect = ? WHERE user_id = ? AND building_id = ?",
                    (now.isoformat(), user_id, b_id),
                )

            if earned["coins"] > 0:
                await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (earned["coins"], user_id))
            if earned["gold"] > 0:
                await db.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (earned["gold"], user_id))
            await db.commit()

    if earned["coins"] > 0 or earned["gold"] > 0:
        await update_mission_progress(user_id, "collect_resource", 1)

    return earned


# ==================== ارتش و رتبه‌بندی ====================
async def get_army(user_id: int) -> dict:
    rows = await db_fetchall("SELECT * FROM user_army WHERE user_id = ?", (user_id,))
    army = {r["unit_id"]: r["count"] for r in rows}
    for unit_id in UNIT_ORDER:
        army.setdefault(unit_id, 0)
    return army


async def calc_total_power(user_id: int, user: dict = None, army: dict = None) -> int:
    if user is None:
        user = await get_user(user_id)
    if army is None:
        army = await get_army(user_id)

    raw_power = sum(UNITS[u_id]["power"] * count for u_id, count in army.items())
    level_bonus = (user["level"] - 1) * 5 if user else 0  # هر لول یه بونوس رهبری کوچیک میده
    bonus = country_bonus(user.get("country") if user else None, "military_pct")
    return int((raw_power + level_bonus) * (1 + bonus))


async def update_military_power(user_id: int):
    power = await calc_total_power(user_id)
    await db_execute("UPDATE users SET military_power = ? WHERE user_id = ?", (power, user_id), commit=True)
    return power


async def recruit_unit(user_id: int, unit_id: str, quantity: int = 1):
    """تلاش برای استخدام تعدادی از یک واحد نظامی. خروجی: (success: bool, message: str)"""
    if unit_id not in UNITS:
        return False, "واحد نامعتبره."
    if quantity <= 0:
        return False, "تعداد نامعتبره."

    async with get_user_lock(user_id):
        user = await get_user(user_id)
        if not user:
            return False, "اول باید ثبت‌نام کنی، دستور /start رو بزن."

        buildings = await get_user_buildings(user_id)
        barracks_level = buildings.get("barracks", {}).get("level", 0)
        unit = UNITS[unit_id]

        if barracks_level < unit["unlock_level"]:
            return False, f"برای استخدام {unit['name']} باید پادگان رو حداقل به سطح {unit['unlock_level']} برسونی."

        army = await get_army(user_id)
        current_total = sum(army.values())
        capacity = army_capacity(barracks_level)
        if current_total + quantity > capacity:
            return False, f"ظرفیت ارتشت پره! ({current_total}/{capacity}) — پادگان رو ارتقا بده تا ظرفیت بیشتر بشه."

        cost_coins = unit["cost_coins"] * quantity
        cost_gold = unit["cost_gold"] * quantity
        if user["coins"] < cost_coins:
            return False, f"سکه کافی نداری! نیاز: {_fmt(cost_coins)} — موجودی: {_fmt(user['coins'])}"
        if user["gold"] < cost_gold:
            return False, f"طلای کافی نداری! نیاز: {_fmt(cost_gold)} — موجودی: {_fmt(user['gold'])}"

        db = await get_db()
        async with _db_lock:
            await db.execute(
                "UPDATE users SET coins = coins - ?, gold = gold - ? WHERE user_id = ?",
                (cost_coins, cost_gold, user_id),
            )
            await db.execute("""
                INSERT INTO user_army (user_id, unit_id, count) VALUES (?, ?, ?)
                ON CONFLICT(user_id, unit_id) DO UPDATE SET count = count + excluded.count
            """, (user_id, unit_id, quantity))
            await db.commit()

    await update_military_power(user_id)
    return True, f"✅ {quantity}x {unit['name']} استخدام شد!"


async def collect_army_upkeep(user_id: int) -> int:
    """هزینه‌ی نگهداری ارتش رو از آخرین باری که چک شده کم می‌کنه (بدون منفی شدن موجودی). خروجی: مقدار کسرشده."""
    user = await get_user(user_id)
    if not user:
        return 0

    army = await get_army(user_id)
    hourly_upkeep = sum(UNITS[u_id]["upkeep"] * count for u_id, count in army.items())
    if hourly_upkeep <= 0:
        await update_fields(user_id, last_upkeep_update=datetime.utcnow().isoformat())
        return 0

    last_update_raw = user.get("last_upkeep_update") or user.get("last_energy_update") or datetime.utcnow().isoformat()
    try:
        last_update = datetime.fromisoformat(last_update_raw)
    except ValueError:
        last_update = datetime.utcnow()

    elapsed_hours = min((datetime.utcnow() - last_update).total_seconds() / 3600, 24)  # سقف ۲۴ ساعت
    due = int(hourly_upkeep * elapsed_hours)
    charged = min(due, user["coins"])  # موجودی هیچ‌وقت منفی نمی‌شه

    await update_fields(
        user_id,
        coins=user["coins"] - charged,
        last_upkeep_update=datetime.utcnow().isoformat(),
    )
    return charged


async def get_leaderboard(limit: int = 10):
    return await db_fetchall(
        "SELECT user_id, full_name, level, military_power, country FROM users "
        "WHERE is_registered = 1 ORDER BY military_power DESC, level DESC LIMIT ?",
        (limit,),
    )


async def get_user_rank(user_id: int) -> int:
    user = await get_user(user_id)
    if not user:
        return 0
    row = await db_fetchone(
        "SELECT COUNT(*) + 1 AS rnk FROM users WHERE is_registered = 1 AND military_power > ?",
        (user["military_power"] or 0,),
    )
    return row["rnk"] if row else 1


# ==================== سیستم نبرد ====================
async def get_random_opponent(user_id: int):
    """یک حریف تصادفی ثبت‌نام‌شده به‌جز خود کاربر برمی‌گردونه."""
    rows = await db_fetchall(
        "SELECT user_id, full_name, level, military_power, country FROM users "
        "WHERE is_registered = 1 AND user_id != ? ORDER BY RANDOM() LIMIT 1",
        (user_id,),
    )
    return rows[0] if rows else None


async def _apply_battle_result(user_id: int, won: bool, enemy_power: int, is_pvp: bool) -> dict:
    user = await get_user(user_id)

    if won:
        base_coins = 40 + enemy_power // 8
        base_xp = 15 + enemy_power // 20
        reward_coins = int(base_coins * random.uniform(0.85, 1.15))
        reward_xp = int(base_xp * random.uniform(0.85, 1.15))
        hp_loss = random.randint(BATTLE_HP_LOSS_MIN_WIN, BATTLE_HP_LOSS_MAX_WIN)
    else:
        reward_coins = 0
        reward_xp = 5
        hp_loss = random.randint(BATTLE_HP_LOSS_MIN_LOSE, BATTLE_HP_LOSS_MAX_LOSE)

    new_hp = max(1, user["hp"] - hp_loss)  # جان هیچ‌وقت صفر نمیشه که کاربر قفل نمونه
    new_energy = max(0, user["energy"] - BATTLE_ENERGY_COST)
    wins = (user.get("wins") or 0) + (1 if won else 0)
    losses = (user.get("losses") or 0) + (0 if won else 1)

    await update_fields(user_id, hp=new_hp, energy=new_energy, wins=wins, losses=losses)

    if reward_coins:
        await add_coins(user_id, reward_coins)
    levels_gained = await add_xp(user_id, reward_xp) if reward_xp else []

    if not is_pvp:
        await update_mission_progress(user_id, "battle_bot", 1)
    if won:
        await update_mission_progress(user_id, "battle_win", 1)

    return {
        "won": won,
        "reward_coins": reward_coins,
        "reward_xp": reward_xp,
        "hp_loss": hp_loss,
        "new_hp": new_hp,
        "new_energy": new_energy,
        "levels_gained": levels_gained,
    }


async def battle_pve(user_id: int):
    """نبرد با یه حریف مصنوعی که قدرتش حول قدرت خود بازیکن شبیه‌سازی میشه."""
    async with get_user_lock(user_id):
        await regen_all(user_id)
        user = await get_user(user_id)
        if not user:
            return False, "اول باید ثبت‌نام کنی، دستور /start رو بزن.", None
        if user["energy"] < BATTLE_ENERGY_COST:
            return False, f"⚡️ انرژی کافی نداری! نیاز: {BATTLE_ENERGY_COST} — موجودی: {user['energy']}", None
        if user["hp"] < BATTLE_MIN_HP:
            return False, f"❤️ جونت خیلی کمه! حداقل {BATTLE_MIN_HP} جان لازمه، کمی صبر کن تا جونت پر بشه.", None

        my_power = max(await calc_total_power(user_id, user=user), 10)
        enemy_power = max(5, int(my_power * random.uniform(0.75, 1.25)))
        win_chance = _clamp(my_power / (my_power + enemy_power), 0.15, 0.9)
        won = random.random() < win_chance

        result = await _apply_battle_result(user_id, won, enemy_power, is_pvp=False)
        result["enemy_power"] = enemy_power
        result["my_power"] = my_power
        return True, None, result


async def battle_pvp(user_id: int):
    """حمله تصادفی به یکی دیگه از فرمانده‌های ثبت‌نام‌شده."""
    async with get_user_lock(user_id):
        await regen_all(user_id)
        user = await get_user(user_id)
        if not user:
            return False, "اول باید ثبت‌نام کنی، دستور /start رو بزن.", None
        if user["energy"] < BATTLE_ENERGY_COST:
            return False, f"⚡️ انرژی کافی نداری! نیاز: {BATTLE_ENERGY_COST} — موجودی: {user['energy']}", None
        if user["hp"] < BATTLE_MIN_HP:
            return False, f"❤️ جونت خیلی کمه! حداقل {BATTLE_MIN_HP} جان لازمه، کمی صبر کن تا جونت پر بشه.", None

        opponent = await get_random_opponent(user_id)
        if not opponent:
            return False, "فرمانده دیگه‌ای برای حمله پیدا نشد؛ بعداً دوباره امتحان کن.", None

        my_power = max(await calc_total_power(user_id, user=user), 10)
        enemy_power = max(opponent["military_power"] or 10, 10)
        win_chance = _clamp(my_power / (my_power + enemy_power), 0.1, 0.85)
        won = random.random() < win_chance

        result = await _apply_battle_result(user_id, won, enemy_power, is_pvp=True)
        result["enemy_power"] = enemy_power
        result["my_power"] = my_power
        result["opponent_name"] = opponent["full_name"]
        result["opponent_country"] = opponent["country"]
        return True, None, result


# ==================== کیبوردها و متن‌های UI ====================
def _header(title: str) -> str:
    return f"{title}\n━━━━━━━━━━━━━━\n"


def _progress_bar(current: int, total: int, length: int = 10) -> str:
    if not total:
        return "▱" * length
    ratio = _clamp(current / total, 0, 1)
    filled = int(length * ratio)
    return "▰" * filled + "▱" * (length - filled)


def country_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, data in COUNTRIES.items():
        builder.button(text=data["name"], callback_data=f"country:{code}")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 پروفایل من", callback_data="menu:profile")
    builder.button(text="🎯 ماموریت‌ها", callback_data="menu:missions")
    builder.button(text="⚔️ نبرد", callback_data="menu:battle")
    builder.button(text="🏛 امپراتوری من", callback_data="menu:army")
    builder.button(text="🏆 رتبه‌بندی جهانی", callback_data="menu:leaderboard")
    builder.button(text="🌍 اتحاد", callback_data="menu:alliance")
    builder.button(text="🏪 بازار و فروشگاه", callback_data="menu:market")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def back_kb(target: str, label: str = "⬅️ بازگشت") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=label, callback_data=target)
    return builder.as_markup()


def profile_text(display_name: str, user: dict, rank: int) -> str:
    country = COUNTRIES.get(user["country"], {}).get("name", "نامشخص")
    xp_bar = _progress_bar(user["xp"], user["xp_needed"])
    hp_bar = _progress_bar(user["hp"], user["max_hp"])
    energy_bar = _progress_bar(user["energy"], user["max_energy"])

    return (
        f"{_header(f'👤 پروفایل {display_name}')}"
        f"🌍 کشور: {country}\n"
        f"📊 لول: <b>{user['level']}</b>\n\n"
        f"✨ XP: {user['xp']}/{user['xp_needed']}\n{xp_bar}\n\n"
        f"❤️ جان: {user['hp']}/{user['max_hp']}\n{hp_bar}\n\n"
        f"⚡️ انرژی: {user['energy']}/{user['max_energy']}\n{energy_bar}\n\n"
        f"💰 سکه: {_fmt(user['coins'])}\n"
        f"🪙 طلا: {_fmt(user['gold'])}\n"
        f"💪 قدرت نظامی: {_fmt(user['military_power'] or 0)} (رتبه #{rank})\n"
        f"🏆 برد/باخت: {user.get('wins') or 0} / {user.get('losses') or 0}"
    )


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
            label = f"{b['name']} (سطح {level}) ⬆️ {_fmt(cost)}{resource_icon}"
        builder.button(text=label, callback_data=f"build:upgrade:{b_id}")
    builder.button(text="💰 برداشت درآمد", callback_data="build:collect")
    builder.button(text="⬅️ بازگشت", callback_data="menu:army")
    builder.adjust(1)
    return builder.as_markup()


def buildings_text(buildings: dict) -> str:
    lines = [_header("🏗 ساختمان‌های کشور")]
    for b_id in BUILDING_ORDER:
        b = BUILDINGS[b_id]
        level = buildings.get(b_id, {}).get("level", 0)
        if b.get("currency"):
            per_hour = building_production_per_hour(b_id, level)
            icon = "💰" if b["currency"] == "coins" else "🪙"
            lines.append(f"{b['name']} — سطح {level} — تولید: {_fmt(per_hour)}{icon}/ساعت")
        elif b_id == "barracks":
            capacity = army_capacity(level)
            lines.append(f"{b['name']} — سطح {level} — ظرفیت ارتش: {capacity} نیرو")
        else:
            cap_hours = building_storage_cap_hours(level)
            lines.append(f"{b['name']} — سطح {level} — ظرفیت انباشت تولید: {cap_hours} ساعت")
    lines.append(
        "\nهر ساختمان رو ارتقا بده تا کشورت قوی‌تر بشه.\n"
        "⚠️ یادت نره سر وقت درآمدت رو برداشت کنی، چون تولید بیشتر از ظرفیت انبار هدر میره!"
    )
    return "\n".join(lines)


def army_hub_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏗 ساختمان‌های کشور", callback_data="menu:buildings")
    builder.button(text="⚔️ نیروی نظامی من", callback_data="menu:military")
    builder.button(text="🏆 رتبه‌بندی جهانی", callback_data="menu:leaderboard")
    builder.button(text="⬅️ بازگشت", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def military_hub_text(buildings: dict, army: dict) -> str:
    barracks_level = buildings.get("barracks", {}).get("level", 0)
    capacity = army_capacity(barracks_level)
    total_units = sum(army.values())
    hourly_upkeep = sum(UNITS[u_id]["upkeep"] * count for u_id, count in army.items())
    breakdown = unit_power_breakdown(army)

    lines = [
        _header("🏰 ستاد فرماندهی نظامی"),
        f"🎖 سطح پادگان: {barracks_level}",
        f"👥 نیروی کل: {total_units}/{capacity}",
        f"💸 هزینه نگهداری: {_fmt(hourly_upkeep)} سکه/ساعت",
        "",
        "<b>💪 قدرت به‌تفکیک نیرو:</b>",
    ]
    for cat in CATEGORY_ORDER:
        lines.append(f"{CATEGORIES[cat]['label']}: {_fmt(breakdown[cat])}")
    lines.append("")
    lines.append("یکی از بخش‌های زیر رو انتخاب کن تا نیرو استخدام کنی:")
    return "\n".join(lines)


def military_hub_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in CATEGORY_ORDER:
        builder.button(text=CATEGORIES[cat]["label"], callback_data=f"army:cat:{cat}")
    builder.button(text="⬅️ بازگشت", callback_data="menu:army")
    builder.adjust(2)
    return builder.as_markup()


def category_units_text(category: str, army: dict, barracks_level: int) -> str:
    lines = [_header(CATEGORIES[category]["label"])]
    for unit_id in UNITS_BY_CATEGORY[category]:
        unit = UNITS[unit_id]
        count = army.get(unit_id, 0)
        if barracks_level < unit["unlock_level"]:
            lines.append(f"🔒 {unit['name']} — نیاز: پادگان سطح {unit['unlock_level']}")
        else:
            gold_part = f" + {_fmt(unit['cost_gold'])}🪙" if unit["cost_gold"] else ""
            lines.append(
                f"{unit['name']} — دارم: {count} — قدرت واحد: {_fmt(unit['power'])} — "
                f"هزینه: {_fmt(unit['cost_coins'])}💰{gold_part}"
            )
    if not UNITS_BY_CATEGORY[category]:
        lines.append("فعلاً واحدی در این دسته تعریف نشده.")
    return "\n".join(lines)


def category_units_kb(category: str, barracks_level: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for unit_id in UNITS_BY_CATEGORY[category]:
        unit = UNITS[unit_id]
        if barracks_level < unit["unlock_level"]:
            builder.button(text=f"🔒 {unit['name']}", callback_data="locked:unit")
            continue
        builder.button(text=f"{unit['name']} ۱x", callback_data=f"recruit:{unit_id}:1")
        builder.button(text=f"{unit['name']} ۱۰x", callback_data=f"recruit:{unit_id}:10")
    builder.button(text="⬅️ بازگشت", callback_data="menu:military")
    builder.adjust(2)
    return builder.as_markup()


def leaderboard_text(rows: list, me_rank: int, me_power: int) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines = [_header("🏆 رتبه‌بندی جهانی فرمانده‌ها")]
    if not rows:
        lines.append("هنوز هیچ فرمانده‌ای ثبت‌نام نکرده.")
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        country = COUNTRIES.get(row["country"], {}).get("name", "❓")
        lines.append(f"{medal} {row['full_name']} — {country} — لول {row['level']} — 💪 {_fmt(row['military_power'])}")
    lines.append(f"\n📍 رتبه‌ی تو: #{me_rank} — قدرت نظامی: {_fmt(me_power)}💪")
    return "\n".join(lines)


def battle_menu_text(user: dict) -> str:
    return (
        f"{_header('⚔️ میدان نبرد')}"
        f"⚡️ انرژی: {user['energy']}/{user['max_energy']}\n"
        f"❤️ جان: {user['hp']}/{user['max_hp']}\n"
        f"🏆 برد/باخت: {user.get('wins') or 0} / {user.get('losses') or 0}\n\n"
        f"هر نبرد {BATTLE_ENERGY_COST}⚡️ انرژی مصرف می‌کنه و حداقل {BATTLE_MIN_HP}❤️ جان لازم داره.\n\n"
        f"🤖 <b>نبرد با ربات:</b> حریف بر اساس قدرت خودت شبیه‌سازی میشه.\n"
        f"🎯 <b>حمله تصادفی:</b> با یکی از فرمانده‌های دیگه رودررو میشی!"
    )


def battle_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 نبرد با ربات (PvE)", callback_data="battle:pve")
    builder.button(text="🎯 حمله تصادفی (PvP)", callback_data="battle:pvp")
    builder.button(text="⬅️ بازگشت", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def battle_result_text(result: dict) -> str:
    won = result["won"]
    header = "🎉 پیروز شدی!" if won else "💥 شکست خوردی!"
    lines = [_header(header)]

    opponent_name = result.get("opponent_name")
    if opponent_name:
        country = COUNTRIES.get(result.get("opponent_country"), {}).get("name", "❓")
        lines.append(f"🎯 حریف: {opponent_name} ({country})")
    else:
        lines.append("🎯 حریف: نیروهای شبیه‌سازی‌شده 🤖")

    lines.append(f"💪 قدرت تو: {_fmt(result['my_power'])} | قدرت حریف: {_fmt(result['enemy_power'])}")
    if won and result["reward_coins"]:
        lines.append(f"🪙 غنیمت جنگی: +{_fmt(result['reward_coins'])} سکه")
    lines.append(f"✨ تجربه: +{_fmt(result['reward_xp'])} XP")
    lines.append(f"❤️ آسیب دیده: -{result['hp_loss']} (جان فعلی: {result['new_hp']})")
    lines.append(f"⚡️ انرژی باقیمانده: {result['new_energy']}")

    if result.get("levels_gained"):
        lvls = "، ".join(str(l) for l in result["levels_gained"])
        lines.append(f"\n🎊 لول‌آپ شدی! لول جدید: {lvls}")

    return "\n".join(lines)


# ==================== هندلرها ====================
router = Router()

COMING_SOON = {
    "menu:alliance": "🌍 سیستم اتحاد به‌زودی اضافه میشه!",
    "menu:market": "🏪 بازار و فروشگاه به‌زودی اضافه میشه!",
}


def safe_message(handler):
    """هر خطای غیرمنتظره‌ای رو می‌گیره تا کل ربات کرش نکنه."""
    async def wrapper(message: Message, *args, **kwargs):
        try:
            await handler(message, *args, **kwargs)
        except Exception:
            logger.exception("خطا در پردازش پیام (handler=%s)", getattr(handler, "__name__", handler))
            try:
                await message.answer("⚠️ یه خطای غیرمنتظره پیش اومد، لطفاً دوباره امتحان کن.")
            except Exception:
                logger.exception("ارسال پیام خطا هم شکست خورد")
    wrapper.__name__ = getattr(handler, "__name__", "handler")
    return wrapper


def safe_callback(handler):
    """هر خطای غیرمنتظره‌ای رو می‌گیره تا کل ربات کرش نکنه."""
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        try:
            await handler(callback, *args, **kwargs)
        except Exception:
            logger.exception("خطا در پردازش callback (handler=%s, data=%s)", getattr(handler, "__name__", handler), callback.data)
            try:
                await callback.answer("⚠️ یه خطای غیرمنتظره پیش اومد، دوباره امتحان کن.", show_alert=True)
            except Exception:
                logger.exception("ارسال پاسخ خطا هم شکست خورد")
    wrapper.__name__ = getattr(handler, "__name__", "handler")
    return wrapper


@router.message(CommandStart())
@safe_message
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
@safe_callback
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
@safe_callback
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    await regen_all(user_id)
    await collect_army_upkeep(user_id)
    user = await get_user(user_id)
    if not user:
        await callback.answer("اول باید ثبت‌نام کنی، دستور /start رو بزن.", show_alert=True)
        return

    rank = await get_user_rank(user_id)
    await callback.message.edit_text(
        profile_text(callback.from_user.full_name, user, rank),
        reply_markup=back_kb("menu:main"),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:main")
@safe_callback
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 منوی اصلی — بخش موردنظرت رو انتخاب کن:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:missions")
@safe_callback
async def show_missions(callback: CallbackQuery):
    missions = await get_daily_missions(callback.from_user.id)
    await callback.message.edit_text(
        _header("🎯 ماموریت‌های امروز") + "هر ماموریت رو کامل کن و جایزه‌شو بگیر:",
        reply_markup=missions_kb(missions),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("claim_mission:"))
@safe_callback
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
        _header("🎯 ماموریت‌های امروز") + "هر ماموریت رو کامل کن و جایزه‌شو بگیر:",
        reply_markup=missions_kb(missions),
    )


@router.callback_query(F.data == "menu:army")
@safe_callback
async def show_army_hub(callback: CallbackQuery):
    await collect_army_upkeep(callback.from_user.id)
    await callback.message.edit_text(
        _header("🏛 امپراتوری من") + "از اینجا کشورت رو بساز و نیروی نظامیت رو مدیریت کن:",
        reply_markup=army_hub_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:buildings")
@safe_callback
async def show_buildings(callback: CallbackQuery):
    buildings = await get_user_buildings(callback.from_user.id)
    await callback.message.edit_text(
        buildings_text(buildings),
        reply_markup=buildings_kb(buildings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("build:upgrade:"))
@safe_callback
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
@safe_callback
async def handle_collect_income(callback: CallbackQuery):
    earned = await collect_building_income(callback.from_user.id)

    if earned["coins"] == 0 and earned["gold"] == 0:
        await callback.answer("چیزی برای برداشت نیست، صبر کن ساختمان‌هات تولید کنن.", show_alert=True)
    else:
        parts = []
        if earned["coins"] > 0:
            parts.append(f"{_fmt(earned['coins'])} سکه")
        if earned["gold"] > 0:
            parts.append(f"{_fmt(earned['gold'])} طلا")
        await callback.answer(f"🎉 برداشت شد: {' و '.join(parts)}", show_alert=True)

    buildings = await get_user_buildings(callback.from_user.id)
    await callback.message.edit_text(
        buildings_text(buildings),
        reply_markup=buildings_kb(buildings),
    )


@router.callback_query(F.data == "menu:military")
@safe_callback
async def show_military_hub(callback: CallbackQuery):
    user_id = callback.from_user.id
    await collect_army_upkeep(user_id)
    buildings = await get_user_buildings(user_id)
    army = await get_army(user_id)

    await callback.message.edit_text(
        military_hub_text(buildings, army),
        reply_markup=military_hub_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("army:cat:"))
@safe_callback
async def show_category_units(callback: CallbackQuery):
    category = callback.data.split(":")[2]
    if category not in CATEGORIES:
        await callback.answer("دسته نامعتبره.", show_alert=True)
        return

    user_id = callback.from_user.id
    buildings = await get_user_buildings(user_id)
    army = await get_army(user_id)
    barracks_level = buildings.get("barracks", {}).get("level", 0)

    await callback.message.edit_text(
        category_units_text(category, army, barracks_level),
        reply_markup=category_units_kb(category, barracks_level),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recruit:"))
@safe_callback
async def handle_recruit(callback: CallbackQuery):
    _, unit_id, qty_str = callback.data.split(":")
    quantity = int(qty_str)

    success, msg = await recruit_unit(callback.from_user.id, unit_id, quantity)
    await callback.answer(msg, show_alert=True)

    category = UNITS.get(unit_id, {}).get("category", CATEGORY_ORDER[0])
    user_id = callback.from_user.id
    buildings = await get_user_buildings(user_id)
    army = await get_army(user_id)
    barracks_level = buildings.get("barracks", {}).get("level", 0)

    await callback.message.edit_text(
        category_units_text(category, army, barracks_level),
        reply_markup=category_units_kb(category, barracks_level),
    )


@router.callback_query(F.data == "locked:unit")
@safe_callback
async def handle_locked_unit(callback: CallbackQuery):
    await callback.answer("این واحد هنوز قفله! پادگانت رو ارتقا بده.", show_alert=True)


@router.callback_query(F.data == "menu:leaderboard")
@safe_callback
async def show_leaderboard(callback: CallbackQuery):
    user_id = callback.from_user.id
    await update_military_power(user_id)
    rows = await get_leaderboard(10)
    rank = await get_user_rank(user_id)
    user = await get_user(user_id)

    await callback.message.edit_text(
        leaderboard_text(rows, rank, user["military_power"] or 0),
        reply_markup=back_kb("menu:main"),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:battle")
@safe_callback
async def show_battle_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    await regen_all(user_id)
    user = await get_user(user_id)
    if not user:
        await callback.answer("اول باید ثبت‌نام کنی، دستور /start رو بزن.", show_alert=True)
        return

    await callback.message.edit_text(
        battle_menu_text(user),
        reply_markup=battle_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "battle:pve")
@safe_callback
async def handle_battle_pve(callback: CallbackQuery):
    user_id = callback.from_user.id
    ok, err, result = await battle_pve(user_id)
    if not ok:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer("⚔️ نتیجه نبرد آماده شد!")
    await callback.message.edit_text(
        battle_result_text(result),
        reply_markup=battle_menu_kb(),
    )

    user = await get_user(user_id)
    if user:
        await callback.message.answer(
            battle_menu_text(user),
            reply_markup=battle_menu_kb(),
        )


@router.callback_query(F.data == "battle:pvp")
@safe_callback
async def handle_battle_pvp(callback: CallbackQuery):
    user_id = callback.from_user.id
    ok, err, result = await battle_pvp(user_id)
    if not ok:
        await callback.answer(err, show_alert=True)
        return

    await callback.answer("⚔️ نتیجه نبرد آماده شد!")
    await callback.message.edit_text(
        battle_result_text(result),
        reply_markup=battle_menu_kb(),
    )


@router.callback_query(F.data.in_(COMING_SOON.keys()))
@safe_callback
async def coming_soon(callback: CallbackQuery):
    await callback.answer(COMING_SOON[callback.data], show_alert=True)


# ==================== اجرا ====================
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "❌ توکن ربات تنظیم نشده! متغیر محیطی BOT_TOKEN رو ست کن یا مقدار "
            "BOT_TOKEN بالای فایل رو با توکن واقعی ربات جایگزین کن."
        )

    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("ربات در حال اجراست...")
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("ربات متوقف شد.")
