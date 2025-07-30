from modules.telegram_handler import app
import asyncio, logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("» starting TomaiSignalAI …")
    asyncio.run(app.run_polling())
