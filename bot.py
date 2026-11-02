import logging
import os
import datetime
import asyncio
import sqlite3  # 👈 Added this import to fix the NameError
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import database as db

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PT Reminder!\n\n"
        "Commands:\n"
        "/remind <seconds> <message> - Set a one-time reminder\n"
        "/daily <HH:MM> <message> - Set a daily group announcement"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        seconds = int(context.args[0])
        text = " ".join(context.args[1:])
        if not text:
            raise ValueError
            
        remind_at = (datetime.datetime.now() + datetime.timedelta(seconds=seconds)).isoformat()
        db.add_reminder(update.effective_chat.id, text, remind_at)
        await update.message.reply_text(f"✅ Reminder set for {seconds} seconds from now.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /remind <seconds> <message>")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = context.args[0]  # Expect HH:MM
        text = " ".join(context.args[1:])
        if not text:
            raise ValueError
            
        hour, minute = map(int, time_str.split(":"))
        
        # 1. Store recurring job in DB
        with sqlite3.connect(db.DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO recurring (chat_id, text, hour, minute) VALUES (?, ?, ?, ?)",
                      (update.effective_chat.id, text, hour, minute))
            conn.commit()
            
        # 2. Add to scheduler immediately so it works without restarting the bot
        scheduler.add_job(
            send_recurring, 
            'cron', 
            hour=hour, 
            minute=minute,
            args=[update.effective_chat.id, text]
        )
        
        await update.message.reply_text(f"🔁 Daily announcement scheduled for {time_str}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /daily <HH:MM> <message>")

# --- Background Worker for One-Time Reminders ---
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now_iso = datetime.datetime.now().isoformat()
    due = db.get_due_reminders(now_iso)
    for rem_id, chat_id, text in due:
        try:
            await context.bot.send_message(chat_id, text=f"⏰ Reminder: {text}")
            db.delete_reminder(rem_id)
        except Exception as e:
            logger.error(f"Failed to send reminder {rem_id}: {e}")

# --- Scheduler for Recurring Reminders ---
async def send_recurring(chat_id, text):
    try:
        await application.bot.send_message(chat_id, text=f"📢 Announcement: {text}")
    except Exception as e:
        logger.error(f"Failed to send recurring announcement to {chat_id}: {e}")

def load_recurring_jobs(scheduler):
    with sqlite3.connect(db.DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id, text, hour, minute FROM recurring")
        for chat_id, text, hour, minute in c.fetchall():
            scheduler.add_job(
                send_recurring, 
                'cron', 
                hour=hour, 
                minute=minute,
                args=[chat_id, text]
            )

# --- Post Init (Runs before the bot starts polling) ---
scheduler = AsyncIOScheduler()

async def post_init(app: Application):
    # Initialize database
    db.init_db()
    # Start the APScheduler
    scheduler.start()
    # Load existing recurring jobs from the database
    load_recurring_jobs(scheduler)
    logger.info("Bot initialized, database connected, and scheduler started.")

# --- Main Application ---
# Note: We pass post_init directly into the builder here
application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("remind", remind))
application.add_handler(CommandHandler("daily", daily))

# Background worker runs every 30 seconds to check for one-time reminders
application.job_queue.run_repeating(check_reminders, interval=30, first=10)

if __name__ == "__main__":
    logger.info("Starting bot...")
    application.run_polling()
