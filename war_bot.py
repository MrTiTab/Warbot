essage, *args, **kwargs)
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
        new_value = min(maximum, current + regen
