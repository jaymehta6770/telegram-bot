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

app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app_web.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# @BotFather se naya token lekar yahan dalein
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_FILE = "database.json"

# -------------------------
# Load database
# -------------------------
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

# -------------------------
# Save database
# -------------------------
def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

EPISODES = load_db()
print("LOADED DB:", EPISODES)

# -------------------------
# AUTO SAVE FROM CHANNEL
# -------------------------
async def auto_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Channel post ya normal message
    msg = update.channel_post or update.message
    if not msg or not msg.caption:
        return

    caption = msg.caption.lower()

    # Pattern: name s01 ep01 720p
    match = re.search(
        r"([\w_]+)\s*s(\d+)\s*ep(\d+)\s*(\d{3,4}p)",
        caption
    )

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

    save_db(EPISODES)
    print(f"Saved: {series} EP{ep} {quality}")
# -------------------------
# START COMMAND
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Welcome! Send series name in start link.")
        return

    series = args[0].lower()
    qualities = EPISODES.get(series)

    if not qualities:
        await update.message.reply_text("Series not found in database.")
        return

    buttons = []
    for q in qualities.keys():
        buttons.append([InlineKeyboardButton(q, callback_data=f"{series}|{q}")])

    await update.message.reply_text(
        "Choose Quality:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# -------------------------
# SEND EPISODES
# -------------------------
async def send_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    series, quality = query.data.split("|")
    files = EPISODES.get(series, {}).get(quality)

    if not files:
        await query.message.reply_text("Episodes not found.")
        return

    await query.message.reply_text(f"Sending {quality} episodes...")

    # 🔥 LOOP — yahin se videos jayenge
    for ep in sorted(files.keys(), key=lambda x: int(x)):
        cap = (
            f"✨ {series.upper()} - EP {ep}\n"
            f"🎬 Quality: {quality}\n"
            f"💖 Powered by @MAKIMA6N_BOT"
        )

        await query.message.reply_video(
            video=files[ep],
            caption=cap
        )
# -------------------------
# APP INITIALIZATION
# -------------------------
# Yahan 'application' use karna Render version ke liye zaroori hai
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(send_quality))
# Sabhi types ke messages/posts ke liye filters.ALL
application.add_handler(MessageHandler(filters.ALL, auto_save))

if __name__ == "__main__":
    print("Bot is starting on NEW SERVICE...")
    keep_alive()
    application.run_polling()
