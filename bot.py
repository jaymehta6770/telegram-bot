import re
import os
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================================================
# 🔐 ENV VARIABLES
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not set in environment")

if not MONGO_URL:
    raise ValueError("❌ MONGO_URL not set in environment")

# =====================================================
# 🍃 MongoDB Connect
# =====================================================

client = MongoClient(MONGO_URL)
db = client["anime_bot"]
collection = db["episodes"]

print("✅ MongoDB Connected")

# =====================================================
# 💾 AUTO SAVE FROM CHANNEL
# Caption format:
# angelnextdoor s01 ep03 1080p
# =====================================================

async def auto_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.message
    if not msg or not msg.caption:
        return

    caption = msg.caption.lower()

    match = re.search(
        r"([\w_]+)\s*s(\d+)\s*ep(\d+)\s*(\d{3,4}p)",
        caption,
    )

    if not match:
        return

    series, season, ep, quality = match.groups()
    series = series.lower()

    file_id = None
    if msg.video:
        file_id = msg.video.file_id
    elif msg.document:
        file_id = msg.document.file_id

    if not file_id:
        return

    collection.update_one(
        {"series": series},
        {
            "$set": {
                f"episodes.s{season}.ep{ep}.{quality}": file_id
            }
        },
        upsert=True,
    )

    print(f"✅ Saved: {series} S{season} EP{ep} {quality}")

# =====================================================
# 🚀 START COMMAND
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # ================= WELCOME =================
    if not args:
        await update.message.reply_text(
            "✨ *WELCOME TO MAKIMA ANIME BOT* ✨\n\n"
            "⚡ Fast Episode Delivery\n"
            "🎬 Multi Quality Available\n"
            "📚 Auto Updated Library\n\n"
            "🔍 Usage:\n"
            "`/start series_s01`\n"
            "`/start series_s01_ep03`\n\n"
            "💖 Powered by @MAKIMA6N_BOT",
            parse_mode="Markdown",
        )
        return

    query = args[0].lower()

    # ================= SINGLE EP =================
    single_match = re.match(r"(.+)_s(\d+)_ep(\d+)", query)

    if single_match:
        series, season, ep = single_match.groups()
        data = collection.find_one({"series": series})

        if not data:
            await update.message.reply_text("❌ Series not found.")
            return

        try:
            qualities = data["episodes"][f"s{season}"][f"ep{ep}"]
        except KeyError:
            await update.message.reply_text("❌ Episode not found.")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    q,
                    callback_data=f"{series}|{season}|{ep}|{q}",
                )
            ]
            for q in qualities.keys()
        ]

        await update.message.reply_text(
            "🎬 Choose Quality:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # ================= FULL SEASON =================

    season_match = re.match(r"(.+)_s(\d+)", query)

    if season_match:
        series, season = season_match.groups()
        data = collection.find_one({"series": series})

        if not data:
            await update.message.reply_text("❌ Series not found.")
            return

        try:
            eps = data["episodes"][f"s{season}"]
        except KeyError:
            await update.message.reply_text("❌ Season not found.")
            return

        text = "📺 Available Episodes:\n\n"
        for ep in sorted(eps.keys()):
            text += f"👉 /start {series}_s{season}_{ep}\n"

        await update.message.reply_text(text)
        return

# =====================================================
# 🎬 SEND VIDEO
# =====================================================

async def send_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    series, season, ep, quality = query.data.split("|")

    data = collection.find_one({"series": series})
    file_id = data["episodes"][f"s{season}"][f"ep{ep}"][quality]

    await query.message.reply_video(
        video=file_id,
        caption=(
            f"✨ {series.upper()} S{season} EP{ep}\n"
            f"🎬 Quality: {quality}\n"
            f"💖 Powered by @MAKIMA6N_BOT"
        ),
    )

# =====================================================
# 🚀 MAIN
# =====================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(send_quality))
    app.add_handler(MessageHandler(filters.ALL, auto_save))

    print("🚀 Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
