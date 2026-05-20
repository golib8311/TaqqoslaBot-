import logging
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FREE_DAILY_LIMIT = 3
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin_username")

users_db = {}

TEXTS = {
    "uz": {
        "welcome": "⚖️ *TaqqoslaBot* — 8 ta saytdan narx qidiraman!\n\n🟠 Uzum • 🟢 OLX • 🔵 Texnomart\n🟡 Asaxiy • 🟤 Mediapark • 🔴 Yandex\n🔷 Ozon • 🟣 Wildberries\n\n🔍 Mahsulot nomini yozing!\n\n📦 Bepul: 3 ta/kun\n👑 Premium: 3,000 so'm/oy",
        "searching": "⏳ Qidirilmoqda...",
        "no_results": "😔 Topilmadi. Boshqa so'z bilan urinib ko'ring.",
        "results_header": "⚖️ *Natijalar:* `{query}`\n\n",
        "best_price": "🏆 *Eng arzon:* {price} so'm — {site}",
        "premium_info": "👑 *Premium*\n\nOylik: 3,000 so'm\nYillik: 10,000 so'm\n\nAdmin bilan bog'laning 👇",
        "status_free": "📊 Reja: Bepul\nBugun: {today}/{limit}\n\n/premium",
        "status_premium": "📊 Reja: 👑 Premium\nMuddat: {until}",
        "limit_reached": "⛔ Kunlik limit tugadi!\n\nBepul: {limit} ta/kun\n\n👑 Premium oling:",
        "payment_info": "💳 Admin ga yozing:\n🆔 ID: `{user_id}`",
        "activated": "✅ Premium faollashtirildi!\nMuddat: {until}",
        "not_admin": "❌ Faqat admin uchun.",
        "error": "⚠️ Xatolik. Qayta urinib ko'ring.",
        "new_search": "🔍 Yangi qidiruv",
        "buy_monthly": "💳 Oylik — 3,000 so'm",
        "buy_yearly": "💎 Yillik — 10,000 so'm",
        "remaining": "📊 Bugun: {today}/{limit}",
        "get_premium": "👑 Premium olish",
    }
}

def t(context, key):
    lang = context.user_data.get("lang", "uz")
    return TEXTS.get(lang, TEXTS["uz"]).get(key, "")

def format_price(price):
    return f"{price:,}".replace(",", " ")

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_user(uid):
    if uid not in users_db:
        users_db[uid] = {"lang": "uz", "searches_today": 0, "last_date": "", "plan": "free", "until": ""}
    return users_db[uid]

def is_premium(uid):
    u = get_user(uid)
    return u["plan"] in ["monthly", "yearly"] and u["until"] >= today_str()

def can_search(uid):
    u = get_user(uid)
    if is_premium(uid):
        return True
    if u["last_date"] != today_str():
        u["searches_today"] = 0
        u["last_date"] = today_str()
    return u["searches_today"] < FREE_DAILY_LIMIT

def do_search(uid):
    u = get_user(uid)
    if u["last_date"] != today_str():
        u["searches_today"] = 0
        u["last_date"] = today_str()
    u["searches_today"] += 1

def searches_today(uid):
    u = get_user(uid)
    if u["last_date"] != today_str():
        return 0
    return u["searches_today"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

async def safe_fetch(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return await r.text()
    except:
        pass
    return None

async def scrape_uzum(s, q):
    html = await safe_fetch(s, f"https://uzum.uz/uz/search?query={q.replace(' ', '+')}")
    res = []
    if not html:
        return res
    try:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".product-card")[:2]:
            try:
                name = el.select_one(".product-card__title").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".product-card__price").get_text()))
                link = "https://uzum.uz" + el.select_one("a")["href"]
                if price:
                    res.append({"site": "Uzum.uz", "emoji": "🟠", "name": name[:45], "price": int(price), "link": link})
            except:
                pass
    except:
        pass
    return res

async def scrape_olx(s, q):
    html = await safe_fetch(s, f"https://www.olx.uz/list/q-{q.replace(' ', '-')}/")
    res = []
    if not html:
        return res
    try:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-cy='l-card']")[:2]:
            try:
                name = el.select_one("h6").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one("[data-testid='ad-price']").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://www.olx.uz{href}" if href.startswith("/") else href
                if price:
                    res.append({"site": "OLX.uz", "emoji": "🟢", "name": name[:45], "price": int(price), "link": link})
            except:
                pass
    except:
        pass
    return res

async def search_all(query):
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(
            scrape_uzum(s, query),
            scrape_olx(s, query),
            return_exceptions=True
        )
    combined = []
    for r in results:
        if isinstance(r, list):
            combined.extend(r)
    return combined

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_user(uid)
    kb = [[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(
        TEXTS["uz"]["welcome"],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💳 Oylik — 3,000 so'm", callback_data="pay_monthly")],
        [InlineKeyboardButton("💎 Yillik — 10,000 so'm", callback_data="pay_yearly")],
        [InlineKeyboardButton("📞 Admin", url=f"https://t.me/{ADMIN_USERNAME}")],
    ]
    await update.message.reply_text(TEXTS["uz"]["premium_info"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_premium(uid):
        text = TEXTS["uz"]["status_premium"].format(until=get_user(uid)["until"])
    else:
        text = TEXTS["uz"]["status_free"].format(today=searches_today(uid), limit=FREE_DAILY_LIMIT)
    await update.message.reply_text(text, parse_mode="Markdown")

async def activate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Faqat admin uchun.")
        return
    try:
        target = int(context.args[0])
        plan = context.args[1]
        days = 30 if plan == "monthly" else 365
        until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        u = get_user(target)
        u["plan"] = plan
        u["until"] = until
        await update.message.reply_text(f"✅ {target} — Premium. Muddat: {until}")
        try:
            await context.bot.send_message(target, f"✅ Premium faollashtirildi!\nMuddat: {until}", parse_mode="Markdown")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}\n/activate USER_ID monthly")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Faqat admin uchun.")
        return
    total = len(users_db)
    prem = sum(1 for u in users_db.values() if u["plan"] in ["monthly","yearly"] and u["until"] >= today_str())
    await update.message.reply_text(f"📊 Jami: {total}\n👑 Premium: {prem}\n🆓 Bepul: {total-prem}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id
    if data.startswith("lang_"):
        lang = data[5:]
        context.user_data["lang"] = lang
        get_user(uid)["lang"] = lang
        await q.edit_message_text(TEXTS["uz"]["welcome"], parse_mode="Markdown")
    elif data in ["pay_monthly", "pay_yearly"]:
        await q.edit_message_text(f"💳 Admin ga yozing:\n🆔 ID: `{uid}`", parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]))
    elif data == "new_search":
        await q.edit_message_text(TEXTS["uz"]["welcome"], parse_mode="Markdown")

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if len(query_text) < 2:
        return
    uid = update.effective_user.id
    if not can_search(uid):
        kb = [[InlineKeyboardButton("💳 Oylik — 3,000 so'm", callback_data="pay_monthly")],
              [InlineKeyboardButton("💎 Yillik — 10,000 so'm", callback_data="pay_yearly")]]
        await update.message.reply_text(
            TEXTS["uz"]["limit_reached"].format(limit=FREE_DAILY_LIMIT),
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return
    msg = await update.message.reply_text("⏳ Qidirilmoqda...")
    try:
        do_search(uid)
        results = await search_all(query_text)
        if not results:
            kb = [[InlineKeyboardButton("🔍 Yangi qidiruv", callback_data="new_search")]]
            await msg.edit_text(TEXTS["uz"]["no_results"], reply_markup=InlineKeyboardMarkup(kb))
            return
        by_site = {}
        for item in results:
            site = item["site"]
            if site not in by_site or item["price"] < by_site[site]["price"]:
                by_site[site] = item
        text = TEXTS["uz"]["results_header"].format(query=query_text)
        for site, item in by_site.items():
            text += f"{item['emoji']} *{site}:*\n   {item['name']}\n   💰 {format_price(item['price'])} so'm\n\n"
        cheapest = min(results, key=lambda x: x["price"])
        text += "─" * 20 + "\n"
        text += TEXTS["uz"]["best_price"].format(price=format_price(cheapest["price"]), site=cheapest["site"])
        if not is_premium(uid):
            text += f"\n\n📊 Bugun: {searches_today(uid)}/{FREE_DAILY_LIMIT}"
        kb = [[InlineKeyboardButton(f"🛒 {cheapest['site']}", url=cheapest["link"])],
              [InlineKeyboardButton("🔍 Yangi qidiruv", callback_data="new_search")]]
        if not is_premium(uid):
            kb.insert(1, [InlineKeyboardButton("👑 Premium olish", callback_data="pay_monthly")])
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(TEXTS["uz"]["error"])

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN kerak!")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("activate", activate_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))
    logger.info("✅ TaqqoslaBot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
