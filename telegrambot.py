import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from main import MobileForexBot
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot_core = MobileForexBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to TomaiSignalBot!\n"
        "Use /analyze EUR/USD or XAU/USD to get started."
    )

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /analyze EUR/USD or XAU/USD")
        return

    pair = context.args[0].upper().replace("/", "")
    result = bot_core.analyze(pair)
    await update.message.reply_text(result, parse_mode="Markdown")

def run_bot():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze))

    print("🤖 Bot is running... Press CTRL+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    run_bot()
