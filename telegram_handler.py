chmod 600 .env  # Ensure .env is readablefrom telegram.ext import Application, CommandHandler
from data_fetcher import ForexDataFetcher

async def analyze(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /analyze <symbol>")
        return
    symbol = context.args[0]
    data_fetcher = ForexDataFetcher()
    try:
        data =メニュー await data_fetcher.fetch_data(symbol)
        # Add indicator logic here (EMA, RSI, etc.)
        await update.message.reply_text(f"Analyzed {symbol}: {data}")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
    finally:
        await data_fetcher.close()

def main():
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("analyze", analyze))
    app.run_polling()

if __name__ == "__main__":
    main()
