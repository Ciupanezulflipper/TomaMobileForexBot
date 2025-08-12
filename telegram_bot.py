#!/usr/bin/env python3
import requests
import time
from main import MinimalForexBot  # This uses your existing analysis logic

BOT_TOKEN = "7991280737:AAGZWG2syFDbG5xhsVoQCNillPLZ8RlcAmk"
CHAT_ID = 6074056245
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(text):
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        requests.post(f"{API_URL}/sendMessage", data=payload)
    except Exception as e:
        print(f"[x] Telegram Error: {e}")

def get_updates():
    try:
        response = requests.get(f"{API_URL}/getUpdates")
        if response.status_code == 200:
            return response.json()
    except:
        return None

def main_loop():
    bot = MinimalForexBot()
    last_update_id = None

    print("🤖 TomaiSignalAI is now listening on Telegram...")

    while True:
        updates = get_updates()
        if not updates or "result" not in updates:
            time.sleep(2)
            continue

        for update in updates["result"]:
            update_id = update["update_id"]
            message = update.get("message", {})
            text = message.get("text", "").lower()

            if last_update_id is None or update_id > last_update_id:
                last_update_id = update_id

                if text == "/analyze":
                    results = bot.run_analysis()
                    for res in results:
                        msg = f"📊 *{res['pair']}*\nPrice: `{res['price']:.5f}`\nEMA9: `{res['ema9']:.5f}`\nEMA21: `{res['ema21']:.5f}`\nRSI: `{res['rsi']:.2f}`\nSignal: *{res['signal']}*"
                        send_message(msg)

                elif text == "/start":
                    send_message("Welcome to TomaiSignalAI. Send /analyze to get signals.")
                elif text == "/status":
                    send_message("Bot is running. Use /analyze to check signals.")
        
        time.sleep(2)

if __name__ == "__main__":
    main_loop()
