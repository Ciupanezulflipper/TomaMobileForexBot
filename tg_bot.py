# tg_bot.py — works with python-telegram-bot v13.x (Termux package)
# Multiple chat IDs, HTML on/off, send as text or file.

import os
from typing import List, Tuple

def _load_env_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    for candidate in (".env", "gpt5_baseline/.env"):
        if os.path.exists(candidate):
            load_dotenv(dotenv_path=candidate)
            break

_load_env_if_present()

def _get_chat_ids() -> List[str]:
    raw = os.getenv("TELEGRAM_CHAT_IDS", "").strip()
    if raw:
        return [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    one = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return [one] if one else []

def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def tg_send(
    text: str,
    html: bool = False,
    as_file: bool = False,
    filename: str = "signal.txt",
) -> bool:
    token = _token()
    chat_ids = _get_chat_ids()
    if not token or not chat_ids:
        print("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS/TELEGRAM_CHAT_ID in .env")
        return False

    try:
        from telegram import Bot, ParseMode
    except Exception as e:
        print(f"Telegram library missing: {e}")
        return False

    bot = Bot(token=token)
    successes = []
    failures: List[Tuple[str, str]] = []

    for cid in chat_ids:
        try:
            if as_file:
                from io import BytesIO
                bio = BytesIO(text.encode("utf-8"))
                bio.name = filename
                bot.send_document(chat_id=cid, document=bio, caption="📎 Attached signal")
            else:
                bot.send_message(
                    chat_id=cid,
                    text=text,
                    parse_mode=(ParseMode.HTML if html else None),
                    disable_web_page_preview=True,
                )
            successes.append(cid)
        except Exception as e:
            failures.append((cid, str(e)))

    if failures:
        for cid, err in failures:
            print(f"Telegram send failed for {cid}: {err}")

    if successes:
        print(f"✅ Telegram: sent to {', '.join(successes)}")
        return True
    else:
        print("❌ Telegram: nothing sent")
        return False

__all__ = ["tg_send"]
