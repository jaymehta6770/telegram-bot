import re
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
from pymongo import MongoClient

# =====================================================
# 🌐 KEEP ALIVE (Render)
# =====================================================
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app_web.run(host='0.0.0.0', port=10000)

def keep_alive():
    Thread(target=run_web).start()

# =====================================================
# 🔐 ENV
# =====================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")

# ⚠️ ONLY YOU CAN UPLOAD (PUT YOUR TELEGRAM ID)
OWNER_ID = int(os.environ.get("5881314349", "0"))

# =====================================================
# 🗄️ MONGO
# =====================================================
client = MongoClient(MONGO_URL)
db = client["anime_bot_db"]
collection = db["episodes"]

def save_to_db(data):
    collection.update_one(
        {"_id": "episodes_data"},
        {"$set": {"content": data}},
        upsert=True
    )

def load_db():
    data = collection.find_one({"_id": "episodes_data"})
    return data["content"] if data else {}

EPISODES = load_db()

# =====================================================
# 🎨 NAME FORMATTER (PHOTO STYLE)
# =====================================================
def pretty_name(raw: str):
    return raw.replace("_", " ").title()

# =====================================================
# ================== UPLOAD HANDLER ===================
# =====================================================
async def save_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # 🔒 only owner upload
    if OWNER_ID and message.from_user.id != OWNER_ID:
        return

    if not message.video:
        return

    caption_text = message.caption
    if not caption_text:
        await message.reply_text("❌ Caption required!")
        return

    try:
        parts = [x.strip() for x in caption_text.split("|")]

        title = parts[0]
        key = title.lower().replace(" ", "")

        # 🎬 MOVIE FORMAT
        if parts[1].upper() == "MOVIE":
            quality = parts[2]
            file_id = message.video.file_id

            EPISODES.setdefault(key, {})
            EPISODES[key][quality] = file_id

        # 📺 SERIES FORMAT
        else:
            season = parts[1].upper()      # S01
            episode = parts[2].upper()     # EP04
            quality = parts[3]             # 720p
            file_id = message.video.file_id

            EPISODES.setdefault(key, {})
            EPISODES[key].setdefault(season, {})
            EPISODES[key][season].setdefault(episode, {})
            EPISODES[key][season][episode][quality] = file_id

        # 💾 SAVE
        save_to_db(EPISODES)

        await message.reply_text("✅ Saved in database!")

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# =====================================================
# 🚀 START COMMAND
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(
            "✨ WELCOME TO MAKIMA ANIME BOT ✨\n\n"
            "Usage:\n"
            "/start angelnextdoor\n"
            "/start angelnextdoor_s01_ep04"
        )
        return

    query = args[0].lower()

    # ========= SINGLE EP =========
    single = re.match(r"(.+)_s(\d+)_ep(\d+)", query)

    if single:
        title, season, ep = single.groups()
        season = f"S{season.zfill(2)}"
        ep = f"EP{ep.zfill(2)}"

        data = EPISODES.get(title)
        if not data:
            await update.message.reply_text("❌ Series not found.")
            return
            files = data.get(season, {}).get(ep)
        if not files:
            await update.message.reply_text("❌ Episode not found.")
            return

        for quality, file_id in files.items():
            cap = (
                f"✨ {pretty_name(title)} {season} - {ep}\n"
                f"🎬 Quality: {quality}\n"
                f"💖 Powered by @MAKIMA6N_BOT"
            )
            await update.message.reply_video(video=file_id, caption=cap)
        return

    # ========= SEASON BUTTON =========
    data = EPISODES.get(query)
    if not data:
        await update.message.reply_text("❌ Series not found.")
        return

    buttons = [
        [InlineKeyboardButton(season, callback_data=f"{query}|{season}")]
        for season in data.keys()
    ]

    await update.message.reply_text(
        "🎬 Choose Season:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# =====================================================
# 📤 SEND SEASON
# =====================================================
async def send_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    title, season = query.data.split("|")
    data = EPISODES.get(title, {}).get(season)

    if not data:
        await query.message.reply_text("❌ Episodes not found.")
        return

    for ep in sorted(data.keys()):
        for quality, file_id in data[ep].items():
            cap = (
                f"✨ {pretty_name(title)} {season} - {ep}\n"
                f"🎬 Quality: {quality}\n"
                f"💖 Powered by @MAKIMA6N_BOT"
            )
            await query.message.reply_video(video=file_id, caption=cap)

# =====================================================
# 🚀 APP INIT
# =====================================================
application = ApplicationBuilder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(send_quality))
application.add_handler(MessageHandler(filters.VIDEO, save_video))

# =====================================================
# ▶️ MAIN
# =====================================================
if __name__ == "__main__":
    print("Bot is starting...")
    keep_alive()
    application.run_polling()
