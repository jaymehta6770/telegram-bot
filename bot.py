import re
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from flask import Flask
from threading import Thread
from pymongo import MongoClient # આ ડેટાબેઝ માટે જરૂરી છે

# -------------------------
# KEEP ALIVE (Render)
# -------------------------
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app_web.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run_web).start()

# -------------------------
# SETTINGS & DATABASE
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# અહીં તમારી MongoDB URL નાખો
MONGO_URL = os.environ.get("MONGO_URL", "તમારી_URL_અહીં") 

client = MongoClient(MONGO_URL)
db = client['anime_bot_db']
collection = db['episodes']

def load_db():
    data = collection.find_one({"_id": "episodes_data"})
    return data['content'] if data else {}

def save_db(data):
    collection.update_one(
        {"_id": "episodes_data"},
        {"$set": {"content": data}},
        upsert=True
    )

EPISODES = load_db()

# =========================================================
# 🔥 AUTO SAVE FROM CHANNEL
# =========================================================
async def auto_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.message
    if not msg or not msg.caption:
        return

    caption = msg.caption.lower()
    match = re.search(r"([\w_]+)\s*s(\d+)\s*ep(\d+)\s*(\d{3,4}p)", caption)

    if not match:
        return

    series, season, ep, quality = match.groups()
    series = f"{series}_s{season}"

    file_id = None
    if msg.video:
        file_id = msg.video.file_id
    elif msg.document:
        file_id = msg.document.file_id

    if not file_id:
        return

    EPISODES.setdefault(series, {}).setdefault(quality, {})
    EPISODES[series][quality][ep] = file_id

    save_db(EPISODES) # આનાથી ડેટા કાયમી સેવ થશે
    print(f"Saved: {series} EP{ep} {quality}")

# =========================================================
# 🚀 START COMMAND (તમારા ઓરિજિનલ મેસેજ સાથે)
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # ================= WELCOME =================
    if not args:
        await update.message.reply_text(
            "✨ WELCOME TO MAKIMA ANIME BOT ✨\n\n"
            "🚀 Fast Episode Delivery\n"
            "🎬 Multi Quality Available\n"
            "📚 Auto Updated Library\n\n"
            "🔍 Usage:\n"
            "/start series_s01\n"
            "/start series_s01_ep3\n\n"
            "💖 Powered by @MAKIMA6N_BOT"
        )
        return

    query = args[0].lower()

    # ================= SINGLE EPISODE MODE =================
    single_match = re.match(r"(.+)_ep(\d+)$", query)

    if single_match:
        series = single_match.group(1)
        ep_req = single_match.group(2)

        qualities = EPISODES.get(series)
        if not qualities:
            await update.message.reply_text("❌ Series not found.")
            return

        sent = False
        for quality, eps in qualities.items():
            if ep_req in eps:
                cap = (
                    f"✨ {series.upper()} - EP {ep_req}\n"
                    f"🎬 Quality: {quality}\n"
                    f"💖 Powered by @MAKIMA6N_BOT"
                )
                await update.message.reply_video(video=eps[ep_req], caption=cap)
                sent = True

        if not sent:
            await update.message.reply_text("❌ Episode not found.")
        return

    # ================= FULL SEASON MODE =================
    series = query
    qualities = EPISODES.get(series)

    if not qualities:
        await update.message.reply_text("❌ Series not found.")
        return
        # અહીં Indentation સુધારેલી છે
    buttons = [
        [InlineKeyboardButton(q, callback_data=f"{series}|{q}")]
        for q in qualities.keys()
    ]

    await update.message.reply_text(
        "🎬 Choose Quality:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# =========================================================
# 📤 SEND FULL SEASON
# =========================================================
async def send_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    series, quality = query.data.split("|")
    files = EPISODES.get(series, {}).get(quality)

    if not files:
        await query.message.reply_text("❌ Episodes not found.")
        return

    await query.message.reply_text(f"🚀 Sending {quality} episodes...")

    for ep in sorted(files.keys(), key=lambda x: int(x)):
        cap = (
            f"✨ {series.upper()} - EP {ep}\n"
            f"🎬 Quality: {quality}\n"
            f"💖 Powered by @MAKIMA6N_BOT"
        )
        await query.message.reply_video(video=files[ep], caption=cap)

# =========================================================
# 🚀 APP INIT
# =========================================================
application = ApplicationBuilder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(send_quality))
application.add_handler(MessageHandler(filters.ALL, auto_save))

# =========================================================
# ▶️ MAIN (સુધારેલું name)
# =========================================================
if name == "main": # અહીં ભૂલ હતી, હવે સુધારી છે
    print("Bot is starting...")
    keep_alive()
    application.run_polling()
