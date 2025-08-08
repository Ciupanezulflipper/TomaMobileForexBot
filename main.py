# main.py — Render-safe starter for python-telegram-bot v20+
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TomaMobileForexBot")

# --- Config ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 TomaMobileForexBot is live (Render)!")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

# --- Main (NO asyncio.run here) ---
def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing (Render env var).")

    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))

    print("🚀 Bot started. Waiting for updates...")
    # Let PTB manage the event loop; don't wrap with asyncio.run().
    # close_loop=False avoids 'Cannot close a running event loop' in some hosts.
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
