import logging
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== SOZLAMALAR =====
FREE_DAILY_LIMIT = 3
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin_username")

# Xotirada saqlanadigan DB
users_db = {}

# ===== TILLAR =====
TEXTS = {
    "uz": {
        "welcome": (
            "⚖️ *TaqqoslaBot* — O'zbekistonning kuchli narx taqqoslash boti!\n\n"
            "🌐 *8 ta saytdan* bir vaqtda qidiraman:\n"
            "🟠 Uzum • 🟢 OLX • 🔵 Texnomart\n"
            "🟡 Asaxiy • 🟤 Mediapark • 🔴 Yandex\n"
            "🔷 Ozon • 🟣 Wildberries\n\n"
            "🔍 Mahsulot nomini yozing!\n\n"
            "📦 *Bepul:* kuniga 3 ta qidiruv\n"
            "👑 *Premium:* oylik 3,000 so'm | yillik 10,000 so'm"
        ),
        "searching": "⏳ *8 ta saytdan qidirilmoqda...*",
        "no_results": "😔 Topilmadi. Boshqa so'z bilan urinib ko'ring.",
        "results_header": "⚖️ *Natijalar:* `{query}`\n\n",
        "best_price": "🏆 *Eng arzon:* {price} so'm — {site}",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set_uz": "✅ O'zbek tili tanlandi!",
        "lang_set_ru": "✅ Русский язык выбран!",
        "lang_set_en": "✅ English selected!",
        "help": (
            "📖 *Yordam*\n\n"
            "/start — Bosh menyu\n"
            "/lang — Tilni o'zgartirish\n"
            "/premium — Obuna ma'lumoti\n"
            "/status — Obuna holati\n\n"
            "💡 Aniq nom kiriting:\n"
            "Masalan: *Samsung A55 128GB*"
        ),
        "premium_info": (
            "👑 *Premium obuna*\n\n"
            "🆓 *Bepul:* kuniga 3 ta qidiruv\n\n"
            "💎 *Premium imkoniyatlari:*\n"
            "• ♾️ Cheksiz qidiruv\n"
            "• Barcha 8 sayt\n"
            "• Tezkor natijalar\n\n"
            "💳 *Narxlar:*\n"
            "• Oylik: 3,000 so'm\n"
            "• Yillik: 10,000 so'm\n"
            "  *(26,000 so'm tejaysiz!)*\n\n"
            "To'lov uchun admin bilan bog'laning 👇"
        ),
        "status_free": "📊 *Holat*\n\nReja: 🆓 Bepul\nBugun: {today}/{limit} qidiruv\n\n👑 /premium",
        "status_premium": "📊 *Holat*\n\nReja: 👑 Premium\nMuddat: {until}\nQidiruvlar: ♾️ Cheksiz",
        "limit_reached": (
            "⛔ *Kunlik limit tugadi!*\n\n"
            "Bepul: kuniga {limit} ta\n"
            "Ertaga yangilanadi.\n\n"
            "👑 *Premium oling:*"
        ),
        "payment_info": (
            "💳 *{plan}* tanlandi!\n\n"
            "Admin ga yozing va ID raqamingizni yuboring:\n"
            "🆔 ID: `{user_id}`\n\n"
            "To'lovdan so'ng admin Premium faollashtiradi."
        ),
        "activated": "✅ *Premium faollashtirildi!*\nMuddat: {until}\n\nEndi cheksiz qidiruv! 🎉",
        "not_admin": "❌ Faqat admin uchun.",
        "error": "⚠️ Xatolik. Qayta urinib ko'ring.",
        "new_search": "🔍 Yangi qidiruv",
        "buy_monthly": "💳 Oylik — 3,000 so'm",
        "buy_yearly": "💎 Yillik — 10,000 so'm",
        "remaining": "📊 Bugungi qidiruvlar: {today}/{limit}",
        "get_premium": "👑 Premium olish",
        "view_site": "🛒 Saytda ko'rish",
    },
    "ru": {
        "welcome": (
            "⚖️ *TaqqoslaBot* — Мощный бот сравнения цен в Узбекистане!\n\n"
            "🌐 Ищу сразу на *8 сайтах:*\n"
            "🟠 Uzum • 🟢 OLX • 🔵 Texnomart\n"
            "🟡 Asaxiy • 🟤 Mediapark • 🔴 Yandex\n"
            "🔷 Ozon • 🟣 Wildberries\n\n"
            "🔍 Напишите название товара!\n\n"
            "📦 *Бесплатно:* 3 поиска в день\n"
            "👑 *Premium:* месяц 3,000 сум | год 10,000 сум"
        ),
        "searching": "⏳ *Поиск на 8 сайтах...*",
        "no_results": "😔 Ничего не найдено. Попробуйте другой запрос.",
        "results_header": "⚖️ *Результаты:* `{query}`\n\n",
        "best_price": "🏆 *Лучшая цена:* {price} сум — {site}",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set_uz": "✅ O'zbek tili tanlandi!",
        "lang_set_ru": "✅ Русский язык выбран!",
        "lang_set_en": "✅ English selected!",
        "help": (
            "📖 *Помощь*\n\n"
            "/start — Главное меню\n"
            "/lang — Сменить язык\n"
            "/premium — Подписка\n"
            "/status — Статус\n\n"
            "💡 Уточняйте запрос:\n"
            "Например: *Samsung A55 128GB*"
        ),
        "premium_info": (
            "👑 *Premium подписка*\n\n"
            "🆓 *Бесплатно:* 3 поиска в день\n\n"
            "💎 *Premium возможности:*\n"
            "• ♾️ Безлимитный поиск\n"
            "• Все 8 сайтов\n"
            "• Быстрые результаты\n\n"
            "💳 *Цены:*\n"
            "• Месяц: 3,000 сум\n"
            "• Год: 10,000 сум\n"
            "  *(экономия 26,000!)*\n\n"
            "Свяжитесь с админом 👇"
        ),
        "status_free": "📊 *Статус*\n\nПлан: 🆓 Бесплатный\nСегодня: {today}/{limit}\n\n👑 /premium",
        "status_premium": "📊 *Статус*\n\nПлан: 👑 Premium\nДо: {until}\nПоиски: ♾️ Безлимит",
        "limit_reached": (
            "⛔ *Лимит исчерпан!*\n\n"
            "Бесплатно: {limit} в день\n"
            "Завтра обновится.\n\n"
            "👑 *Получите Premium:*"
        ),
        "payment_info": (
            "💳 *{plan}* выбран!\n\n"
            "Напишите админу и укажите ID:\n"
            "🆔 ID: `{user_id}`\n\n"
            "После оплаты админ активирует Premium."
        ),
        "activated": "✅ *Premium активирован!*\nДо: {until}\n\nТеперь безлимитный поиск! 🎉",
        "not_admin": "❌ Только для администратора.",
        "error": "⚠️ Ошибка. Попробуйте снова.",
        "new_search": "🔍 Новый поиск",
        "buy_monthly": "💳 Месяц — 3,000 сум",
        "buy_yearly": "💎 Год — 10,000 сум",
        "remaining": "📊 Поиски сегодня: {today}/{limit}",
        "get_premium": "👑 Получить Premium",
        "view_site": "🛒 Открыть сайт",
    },
    "en": {
        "welcome": (
            "⚖️ *TaqqoslaBot* — Uzbekistan's powerful price comparison bot!\n\n"
            "🌐 I search *8 sites* at once:\n"
            "🟠 Uzum • 🟢 OLX • 🔵 Texnomart\n"
            "🟡 Asaxiy • 🟤 Mediapark • 🔴 Yandex\n"
            "🔷 Ozon • 🟣 Wildberries\n\n"
            "🔍 Type a product name!\n\n"
            "📦 *Free:* 3 searches per day\n"
            "👑 *Premium:* monthly 3,000 UZS | yearly 10,000 UZS"
        ),
        "searching": "⏳ *Searching 8 sites...*",
        "no_results": "😔 Nothing found. Try a different search.",
        "results_header": "⚖️ *Results:* `{query}`\n\n",
        "best_price": "🏆 *Best price:* {price} UZS — {site}",
        "choose_lang": "🌐 Choose language:",
        "lang_set_uz": "✅ O'zbek tili tanlandi!",
        "lang_set_ru": "✅ Русский язык выбран!",
        "lang_set_en": "✅ English selected!",
        "help": (
            "📖 *Help*\n\n"
            "/start — Main menu\n"
            "/lang — Change language\n"
            "/premium — Subscription\n"
            "/status — Status\n\n"
            "💡 Be specific:\n"
            "Example: *Samsung A55 128GB*"
        ),
        "premium_info": (
            "👑 *Premium subscription*\n\n"
            "🆓 *Free:* 3 searches per day\n\n"
            "💎 *Premium features:*\n"
            "• ♾️ Unlimited searches\n"
            "• All 8 sites\n"
            "• Fast results\n\n"
            "💳 *Pricing:*\n"
            "• Monthly: 3,000 UZS\n"
            "• Yearly: 10,000 UZS\n"
            "  *(save 26,000!)*\n\n"
            "Contact admin to pay 👇"
        ),
        "status_free": "📊 *Status*\n\nPlan: 🆓 Free\nToday: {today}/{limit}\n\n👑 /premium",
        "status_premium": "📊 *Status*\n\nPlan: 👑 Premium\nUntil: {until}\nSearches: ♾️ Unlimited",
        "limit_reached": (
            "⛔ *Daily limit reached!*\n\n"
            "Free: {limit} per day\n"
            "Resets tomorrow.\n\n"
            "👑 *Get Premium:*"
        ),
        "payment_info": (
            "💳 *{plan}* selected!\n\n"
            "Message admin with your ID:\n"
            "🆔 ID: `{user_id}`\n\n"
            "Admin will activate Premium after payment."
        ),
        "activated": "✅ *Premium activated!*\nUntil: {until}\n\nUnlimited searches now! 🎉",
        "not_admin": "❌ Admin only.",
        "error": "⚠️ Error. Please try again.",
        "new_search": "🔍 New search",
        "buy_monthly": "💳 Monthly — 3,000 UZS",
        "buy_yearly": "💎 Yearly — 10,000 UZS",
        "remaining": "📊 Today's searches: {today}/{limit}",
        "get_premium": "👑 Get Premium",
        "view_site": "🛒 View on site",
    }
}

def t(context, key):
    lang = context.user_data.get("lang", "uz")
    return TEXTS.get(lang, TEXTS["uz"]).get(key, TEXTS["uz"].get(key, ""))

def format_price(price):
    return f"{price:,}".replace(",", " ")

# ===== FOYDALANUVCHI DB =====
def get_user(uid):
    if uid not in users_db:
        users_db[uid] = {
            "lang": "uz", "searches_today": 0,
            "last_date": "", "plan": "free", "until": ""
        }
    return users_db[uid]

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

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

# ===== SCRAPERLAR =====
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
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".product-card")[:2]:
            try:
                name = el.select_one(".product-card__title").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".product-card__price").get_text()))
                link = "https://uzum.uz" + el.select_one("a")["href"]
                if price: res.append({"site": "Uzum.uz", "emoji": "🟠", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_olx(s, q):
    html = await safe_fetch(s, f"https://www.olx.uz/list/q-{q.replace(' ', '-')}/")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-cy='l-card']")[:2]:
            try:
                name = el.select_one("h6").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one("[data-testid='ad-price']").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://www.olx.uz{href}" if href.startswith("/") else href
                if price: res.append({"site": "OLX.uz", "emoji": "🟢", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_texnomart(s, q):
    html = await safe_fetch(s, f"https://texnomart.uz/uz/search?q={q.replace(' ', '+')}")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".product-item, .catalog-item")[:2]:
            try:
                name = el.select_one("h3, h4, .product-name").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".price, .product-price").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://texnomart.uz{href}" if href.startswith("/") else href
                if price: res.append({"site": "Texnomart.uz", "emoji": "🔵", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_asaxiy(s, q):
    html = await safe_fetch(s, f"https://asaxiy.uz/product?key={q.replace(' ', '+')}")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".product-card, .product-item")[:2]:
            try:
                name = el.select_one("h3, .product-card__name, .product-name").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".price, .product-card__price").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://asaxiy.uz{href}" if href.startswith("/") else href
                if price: res.append({"site": "Asaxiy.uz", "emoji": "🟡", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_mediapark(s, q):
    html = await safe_fetch(s, f"https://mediapark.uz/search?q={q.replace(' ', '+')}")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".product-card, .goods-item")[:2]:
            try:
                name = el.select_one("h3, .product-card__name, .goods-name").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".price, .goods-price").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://mediapark.uz{href}" if href.startswith("/") else href
                if price: res.append({"site": "Mediapark.uz", "emoji": "🟤", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_yandex(s, q):
    html = await safe_fetch(s, f"https://market.yandex.ru/search?text={q.replace(' ', '+')}")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-auto='snippet']")[:2]:
            try:
                name = el.select_one("[data-auto='snippet-title']").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one("[data-auto='snippet-price-current']").get_text()))
                href = el.select_one("a")["href"]
                link = f"https://market.yandex.ru{href}" if href.startswith("/") else href
                if price: res.append({"site": "Yandex Market", "emoji": "🔴", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_ozon(s, q):
    html = await safe_fetch(s, f"https://www.ozon.ru/search/?text={q.replace(' ', '+')}")
    res = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select(".tile-root")[:2]:
            try:
                name = el.select_one(".tsBody500Medium, a span").get_text(strip=True)
                price = ''.join(filter(str.isdigit, el.select_one(".price-number, [data-widget='webPrice'] span").get_text()))
                href = el.select_one("a[href*='/product/']")["href"]
                link = f"https://www.ozon.ru{href}" if href.startswith("/") else href
                if price: res.append({"site": "Ozon", "emoji": "🔷", "name": name[:45], "price": int(price), "link": link})
            except: pass
    return res

async def scrape_wildberries(s, q):
    res = []
    try:
        url = f"https://search.wb.ru/exactmatch/ru/common/v5/search?query={q.replace(' ', '+')}&resultset=catalog&limit=5&sort=popular"
        async with s.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                data = await r.json()
                for item in data.get("data", {}).get("products", [])[:2]:
                    name = item.get("name", "")
                    price_rub = item.get("salePriceU", item.get("priceU", 0)) // 100
                    pid = item.get("id", "")
                    if name and price_rub:
                        price_uzs = price_rub * 125  # taxminiy konvertatsiya
                        res.append({
                            "site": "Wildberries", "emoji": "🟣",
                            "name": name[:45], "price": price_uzs,
                            "link": f"https://www.wildberries.ru/catalog/{pid}/detail.aspx"
                        })
    except: pass
    return res

async def search_all(query):
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(
            scrape_uzum(s, query), scrape_olx(s, query),
            scrape_texnomart(s, query), scrape_asaxiy(s, query),
            scrape_mediapark(s, query), scrape_yandex(s, query),
            scrape_ozon(s, query), scrape_wildberries(s, query),
            return_exceptions=True
        )
    combined = []
    for r in results:
        if isinstance(r, list):
            combined.extend(r)
    return combined

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if "lang" not in context.user_data:
        context.user_data["lang"] = u.get("lang", "uz")
    kb = [[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(t(context, "welcome"), parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    ]]
    await update.message.reply_text(t(context, "choose_lang"), reply_markup=InlineKeyboardMarkup(kb))

async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_url = f"https://t.me/{ADMIN_USERNAME}"
    kb = [
        [InlineKeyboardButton(t(context, "buy_monthly"), callback_data="pay_monthly")],
        [InlineKeyboardButton(t(context, "buy_yearly"), callback_data="pay_yearly")],
        [InlineKeyboardButton("📞 Admin", url=admin_url)],
    ]
    await update.message.reply_text(t(context, "premium_info"), parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_premium(uid):
        text = t(context, "status_premium").format(until=get_user(uid)["until"])
    else:
        text = t(context, "status_free").format(today=searches_today(uid), limit=FREE_DAILY_LIMIT)
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(context, "help"), parse_mode="Markdown")

async def activate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /activate user_id monthly|yearly"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(t(context, "not_admin"))
        return
    try:
        target = int(context.args[0])
        plan = context.args[1]
        days = 30 if plan == "monthly" else 365
        until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        u = get_user(target)
        u["plan"] = plan
        u["until"] = until
        await update.message.reply_text(f"✅ {target} — Premium ({plan}) faollashtirildi. Muddat: {until}")
        try:
            await context.bot.send_message(target,
                f"✅ *Premium faollashtirildi!*\nMuddat: {until}\n\nEndi cheksiz qidiruv! 🎉",
                parse_mode="Markdown")
        except: pass
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}\nFoydalanish: /activate USER_ID monthly")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(t(context, "not_admin"))
        return
    total = len(users_db)
    prem = sum(1 for u in users_db.values()
               if u["plan"] in ["monthly","yearly"] and u["until"] >= today_str())
    await update.message.reply_text(
        f"📊 *Statistika*\n\n👥 Jami: {total}\n👑 Premium: {prem}\n🆓 Bepul: {total-prem}",
        parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data.startswith("lang_"):
        lang = data[5:]
        context.user_data["lang"] = lang
        get_user(uid)["lang"] = lang
        key = f"lang_set_{lang}"
        await q.edit_message_text(
            TEXTS[lang][key] + "\n\n" + TEXTS[lang]["welcome"],
            parse_mode="Markdown"
        )
    elif data in ["pay_monthly", "pay_yearly"]:
        plan_name = "Oylik (3,000 so'm)" if data == "pay_monthly" else "Yillik (10,000 so'm)"
        kb = [[InlineKeyboardButton("📞 Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
        await q.edit_message_text(
            t(context, "payment_info").format(plan=plan_name, user_id=uid),
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
    elif data == "new_search":
        await q.edit_message_text(t(context, "welcome"), parse_mode="Markdown")

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if len(query_text) < 2:
        return

    uid = update.effective_user.id

    if not can_search(uid):
        kb = [
            [InlineKeyboardButton(t(context, "buy_monthly"), callback_data="pay_monthly")],
            [InlineKeyboardButton(t(context, "buy_yearly"), callback_data="pay_yearly")],
        ]
        await update.message.reply_text(
            t(context, "limit_reached").format(limit=FREE_DAILY_LIMIT),
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    msg = await update.message.reply_text(t(context, "searching"), parse_mode="Markdown")

    try:
        do_search(uid)
        results = await search_all(query_text)

        if not results:
            kb = [[InlineKeyboardButton(t(context, "new_search"), callback_data="new_search")]]
            await msg.edit_text(t(context, "no_results"), reply_markup=InlineKeyboardMarkup(kb))
            return

        # Saytlar bo'yicha guruhlash
        by_site = {}
        for item in results:
            site = item["site"]
            if site not in by_site or item["price"] < by_site[site]["price"]:
                by_site[site] = item

        text = t(context, "results_header").format(query=query_text)
        for site, item in by_site.items():
            text += f"{item['emoji']} *{site}:*\n"
            text += f"   {item['name']}\n"
            text += f"   💰 {format_price(item['price'])} so'm\n\n"

        cheapest = min(results, key=lambda x: x["price"])
        text += "─" * 20 + "\n"
        text += t(context, "best_price").format(
            price=format_price(cheapest["price"]), site=cheapest["site"]
        )

        if not is_premium(uid):
            text += f"\n\n" + t(context, "remaining").format(
                today=searches_today(uid), limit=FREE_DAILY_LIMIT
            )

        kb = [
            [InlineKeyboardButton(f"🛒 {cheapest['site']}", url=cheapest["link"])],
            [InlineKeyboardButton(t(context, "new_search"), callback_data="new_search")]
        ]
        if not is_premium(uid):
            kb.insert(1, [InlineKeyboardButton(t(context, "get_premium"), callback_data="pay_monthly")])

        await msg.edit_text(text, parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(kb),
                            disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(t(context, "error"))

# ===== MAIN =====
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN kerak!")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("activate", activate_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    logger.info("✅ TaqqoslaBot ishga tushdi! 8 sayt + Obuna tizimi")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
