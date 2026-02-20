from telegram.ext import JobQueue
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

BOT_TOKEN = "8312368923:AAHBPMyhe-8dDq8Mnxf6QNKa4yn2wtoQxfc"
DB_FILE = "database.json"

# -------------------------
# Load database
# -------------------------
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

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
# -------------------------
# AUTO SAVE FROM CHANNEL
# -------------------------
async def auto_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post or not post.caption:
        return

    caption = post.caption.lower()
    match = re.search(r"([a-z0-9]+)\s*s(\d+)\s*ep\s*(\d+)\s*(\d+p)", caption)
    if not match:
        return

    series, season, ep, quality = match.groups()
    series_key = f"{series}_s{season}"

    file_id = None
    if post.video:
        file_id = post.video.file_id
    elif post.document:
        file_id = post.document.file_id

    if not file_id:
        return

    EPISODES.setdefault(series_key, {}).setdefault(quality, {})
    EPISODES[series_key][quality][ep] = file_id

    save_db(EPISODES)

    print(f"Saved permanently: {series} S{season} EP{ep} {quality}")
    
# -------------------------
# START COMMAND
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text("Welcome!")
        return

    # 🔥 handle deep link properly
    data = args[0].lower()

    if "_" in data:
        series, season = data.split("_")
    else:
        series = data
        season = "01"

    series_key = f"{series}_s{season}"

    qualities = EPISODES.get(series_key)

    if not qualities:
        await update.message.reply_text("Series not found.")
        return

    buttons = []
    for q in qualities.keys():
        buttons.append([
            InlineKeyboardButton(q, callback_data=f"{series_key}|{q}")
        ])

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

    series_key, quality = query.data.split("|")
    files = EPISODES.get(series_key, {}).get(quality)

    if not files:
        await query.message.reply_text("Episodes not found.")
        return

    await query.message.reply_text(f"Sending {quality} episodes...")

    # ✅ LOOP START
    for ep in sorted(files.keys(), key=lambda x: int(x)):
        msg = await query.message.reply_video(
            video=files[ep],
            caption=f"✨ {series_key.upper()} EP{ep}\n🎬 Quality: {quality}\n🚀 Powered by @MAKIMA6N_BOT"
        )

        # ✅ AUTO DELETE FUNCTION (INSIDE LOOP)
        async def delete_later(ctx):
            try:
                await ctx.bot.delete_message(
                    chat_id=msg.chat_id,
                    message_id=msg.message_id
                )
            except:
                pass

        context.job_queue.run_once(delete_later, 600)
# -------------------------
# APP
# -------------------------
# APP Initialization
application = ApplicationBuilder().token(BOT_TOKEN).build() # 'app' ki jagah 'application' use karein

application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, auto_save))
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(send_quality))

print("Bot running (Permanent DB version)...")
application.run_polling() # 'app' ki jagah 'application'




