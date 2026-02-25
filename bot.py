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

def clean_key(title: str) -> str:
    return (
        title.lower()
        .replace("&", "and")
        .replace("-", " ")
        .strip()
        .replace("  ", " ")
        .replace(" ", "_")
    )
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
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

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
    message = update.message or update.channel_post

    if not message:
        return

    # 🔒 only owner upload
    if OWNER_ID and message.from_user:
        if message.from_user.id != OWNER_ID:
            return

    # 🎬 get file id
    file_id = None
    if message.video:
        file_id = message.video.file_id
    elif message.document and message.document.mime_type.startswith("video"):
        file_id = message.document.file_id
    else:
        return

    caption_text = message.caption or ""
    if not caption_text:
        await message.reply_text("❌ Caption required!")
        return

    try:
        parts = [x.strip() for x in caption_text.split("|")]

        title = parts[0]
        key = clean_key(title)  # ✅ VERY IMPORTANT FIX

        # 🎬 MOVIE
        if parts[1].upper() == "MOVIE":
            quality = parts[2]

            EPISODES.setdefault(key, {})
            EPISODES[key][quality] = file_id

            print(f"Saved Movie: {title} {quality}")

        # 📺 SERIES
        else:
            season = parts[1].upper()
            episode = parts[2].upper()
            quality = parts[3]

            EPISODES.setdefault(key, {})
            EPISODES[key].setdefault(season, {})
            EPISODES[key][season].setdefault(episode, {})
            EPISODES[key][season][episode][quality] = file_id

            print(f"Saved Series: {title} {season} {episode} {quality}")

        save_to_db(EPISODES)
        print("✅ Mongo Updated")

    except Exception as e:
        print("❌ Save error:", e)
# =====================================================
# 🚀 START COMMAND
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global EPISODES

    try:
        args = context.args
        msg = update.message

        WELCOME_IMG = "https://wallpaperaccess.com/full/15144075.jpg"

        # ================== 🔹 NORMAL START ==================
        if not args:
            buttons = [
                [InlineKeyboardButton("» JOIN CHANNEL «", url="https://t.me/AnimeHdZone")],
                [InlineKeyboardButton("‼️ NOW CLICK HERE ‼️", url="https://t.me/MAKIMA6N_BOT")]
            ]

            await msg.reply_photo(
                photo=WELCOME_IMG,
                caption=f"» HEY 🔥 {update.effective_user.first_name} 🔥 ×,\n\nSUBSCRIBE NOW TO GET YOUR FILES.",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        # reload db if empty
        if not EPISODES:
            EPISODES = load_db()

        query = args[0].lower()

        # =====================================================
        # 🎯 DIRECT QUALITY LINK
        # example: title_s01_ep01_720p
        # =====================================================
        direct_q = re.match(r"(.+)_s(\d+)_ep(\d+)_(\d+p)", query)
        if direct_q:
            title, s_num, e_num, quality = direct_q.groups()

            s_key = f"S{s_num.zfill(2)}"
            e_key = f"EP{e_num.zfill(2)}"

            series = EPISODES.get(title)
            if series:
                file_id = (
                    series
                    .get(s_key, {})
                    .get(e_key, {})
                    .get(quality)
                )

                if file_id:
                    cap = (
                        f"✨ {pretty_name(title)} [{s_key}][{e_key}]\n"
                        f"🎬 Quality: {quality}\n"
                        f"💖 Powered by @MAKIMA6N_BOT"
                    )
                    await msg.reply_video(video=file_id, caption=cap)
                    return

        # =====================================================
        # 🎬 SINGLE EPISODE → SHOW ALL QUALITIES
        # example: title_s01_ep01
        # =====================================================
        single = re.match(r"(.+)_s(\d+)_ep(\d+)", query)
        if single:
            title, s_num, e_num = single.groups()

            s_key = f"S{s_num.zfill(2)}"
            e_key = f"EP{e_num.zfill(2)}"

            series = EPISODES.get(title)
            if series:
                files = series.get(s_key, {}).get(e_key)

                if files:
                    for quality, file_id in files.items():
                        cap = (
                            f"✨ {pretty_name(title)} [{s_key}][{e_key}]\n"
                            f"🎬 Quality: {quality}\n"
                            f"💖 Powered by @MAKIMA6N_BOT"
                        )
                        await msg.reply_video(video=file_id, caption=cap)
                    return
# =====================================================
# 📺 FULL SEASON ONE QUALITY
# example: title_s01_720p
# =====================================================
season_quality = re.match(r"(.+)_s(\d+)_(\d+p)", query)

if season_quality:
    title, s_num, quality = season_quality.groups()

    s_key = f"S{s_num.zfill(2)}"
    series = EPISODES.get(title)

    if series:
        season_data = series.get(s_key)

        if season_data:
            sent = False

            for ep in sorted(season_data.keys()):
                file_id = season_data[ep].get(quality)

                if file_id:
                    sent = True
                    cap = (
                        f"✨ {pretty_name(title)} [{s_key}][{ep}]\n"
                        f"🎬 Quality: {quality}\n"
                        f"💖 Powered by @MAKIMA6N_BOT"
                    )
                    await msg.reply_video(video=file_id, caption=cap)

            if sent:
                return
        # =====================================================
        # 📺 TITLE SEARCH → SHOW SEASONS
        # =====================================================
        data = EPISODES.get(query)
        if not data:
            await msg.reply_text("❌ File not found in Database!")
            return

        seasons = [s for s in data.keys() if s.startswith("S")]

        if seasons:
            buttons = [
                [InlineKeyboardButton(s, callback_data=f"{query}|{s}")]
                for s in sorted(seasons)
            ]

            await msg.reply_text(
                "🎬 Choose Season:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        # =====================================================
        # 🎥 MOVIE CASE
        # =====================================================
        for quality, file_id in data.items():
            cap = (
                f"🎬 {pretty_name(query)}\n"
                f"🎬 Quality: {quality}\n"
                f"💖 Powered by @MAKIMA6N_BOT"
            )
            await msg.reply_video(video=file_id, caption=cap)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        await update.message.reply_text("⚠️ Something went wrong!")

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
application.add_handler(CallbackQueryHandler(send_quality))  # season wala
application.add_handler(MessageHandler(filters.ALL, save_video))
# =====================================================
# ▶️ MAIN
# =====================================================
if __name__ == "__main__":
    print("Bot is starting...")
    keep_alive()
    application.run_polling()
