from datetime import timezone
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
forex_event_scalper.py
- IPv4-forced Telegram sender (fixes [Errno 7] DNS/IPv6 issues)
- Minimal event loop with /ping, manual tone, or auto-disabled mode
- Zero external data APIs required for basic operation

Run examples:
  python forex_event_scalper.py --telegram-token YOUR_TOKEN --chat-id YOUR_CHAT_ID --once --tone ping
  python forex_event_scalper.py --telegram-token YOUR_TOKEN --chat-id YOUR_CHAT_ID --duration 600 --interval 45 --tone auto
"""

import os
import sys
import time
import json
import socket
import argparse
from datetime import datetime
from typing import Optional

# --- Force IPv4 for requests (avoids intermittent IPv6/DNS failures) ---
try:
    import requests
    import requests.packages.urllib3.util.connection as urllib3_cn
    def _allowed_gai_family():
        return socket.AF_INET  # Force IPv4
    urllib3_cn.allowed_gai_family = _allowed_gai_family
except Exception:
    # If this ever fails, we still attempt normal requests
    import requests  # type: ignore

# ---------------- Telegram helpers ----------------

def tg_send(token: str, chat_id: str, text: str, timeout: int = 10, retries: int = 4, backoff: float = 1.5) -> bool:
    """
    Send a Telegram message with IPv4-only sockets, retries, and backoff.
    Returns True on success, False on fail.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],         # Telegram limit
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, data=payload, timeout=timeout)
            if r.status_code == 200:
                return True
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(backoff ** attempt)  # exponential-ish backoff

    sys.stderr.write(f"[tg_send] Failed after {retries} attempts: {last_err}\n")
    return False


# ---------------- Core logic (minimal) ----------------

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"]

TONE_TEMPLATES = {
    "dovish": {
        "EUR/USD": ("BUY", "USD weakness on dovish Fed"),
        "GBP/USD": ("BUY", "USD weakness benefits GBP"),
        "USD/JPY": ("SELL", "USD weakness vs JPY"),
        "AUD/USD": ("BUY", "Risk-on supports AUD"),
        "USD/CAD": ("SELL", "USD weakness vs CAD"),
    },
    "hawkish": {
        "EUR/USD": ("SELL", "USD strength on hawkish Fed"),
        "GBP/USD": ("SELL", "USD strength pressures GBP"),
        "USD/JPY": ("BUY", "USD strength vs JPY"),
        "AUD/USD": ("SELL", "USD strength pressures AUD"),
        "USD/CAD": ("BUY", "USD strength vs CAD"),
    }
}


def format_signal(pair: str, action: str, rationale: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"🚨 *FOREX SCALP SIGNAL* 🚨\n\n"
        f"*Pair*: {pair}\n"
        f"*Action*: {action}\n"
        f"*Rationale*: {rationale}\n"
        f"*Targets*: 10–20 pips | *SL*: 5–10 pips | *Risk*: ≤1%\n"
        f"_Time_: `{now}`"
    )


def run_once(token: str, chat_id: str, tone: str, threshold: int, interval: int) -> None:
    """
    One-shot run:
      - tone=ping    -> send connectivity test
      - tone=auto    -> just send a heartbeat (no API usage)
      - tone=dovish/hawkish -> send a signal pack using templates
    """
    if tone == "ping":
        msg = "✅ *Ping OK* — Telegram reachable. IPv4 forced, retries enabled."
        tg_send(token, chat_id, msg)
        return

    if tone == "auto":
        msg = f"🤖 Event scalper heartbeat — mode=*AUTO*, threshold={threshold} pips, interval={interval}s."
        tg_send(token, chat_id, msg)
        return

    if tone in ("dovish", "hawkish"):
        sent = 0
        for pair, (action, why) in TONE_TEMPLATES[tone].items():
            if tg_send(token, chat_id, format_signal(pair, action, why)):
                sent += 1
        tg_send(token, chat_id, f"✅ Signals sent: {sent}/5 (tone=*{tone}*).")
        return

    tg_send(token, chat_id, f"ℹ️ Unknown tone: `{tone}`. Use ping | auto | dovish | hawkish.")


def run_loop(args) -> None:
    token = args.telegram_token
    chat_id = args.chat_id

    # Startup banner
    start = (
        f"🤖 Event scalper started. Mode=`{args.tone.upper()}` "
        f"| threshold={args.threshold} pips | interval={args.interval}s"
    )
    tg_send(token, chat_id, start)

    # Simple loop; no external APIs in this minimal build
    t_end = time.time() + args.duration
    last_tick = 0
    while time.time() < t_end:
        if args.tone == "auto":
            # Heartbeat every interval
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            tg_send(token, chat_id, f"⏱️ Heartbeat {now} — running (no data APIs).")
        elif args.tone in ("dovish", "hawkish"):
            # Re-broadcast compact reminder each interval
            short = f"📌 Tone=*{args.tone}*. Use pairs: " + ", ".join(PAIRS)
            tg_send(token, chat_id, short)
        else:
            # ping or unknown tone -> just idle
            pass

        time.sleep(args.interval)
        last_tick += 1

    tg_send(token, chat_id, "🛑 Event scalper finished (duration complete).")


def main():
    ap = argparse.ArgumentParser(description="Minimal Forex Event Scalper (Telegram-first, IPv4 forced).")
    ap.add_argument("--telegram-token", required=True, help="Telegram bot token")
    ap.add_argument("--chat-id", required=True, help="Telegram chat ID (user or channel)")
    ap.add_argument("--tone", default="auto", choices=["auto", "dovish", "hawkish", "ping"],
                    help="Signal mode: auto (heartbeat only), dovish, hawkish, or ping for test")
    ap.add_argument("--threshold", type=int, default=10, help="Pip threshold (for future use)")
    ap.add_argument("--interval", type=int, default=45, help="Seconds between sends in loop")
    ap.add_argument("--duration", type=int, default=300, help="Total runtime seconds for loop mode")
    ap.add_argument("--once", action="store_true", help="Run once and exit (no loop)")
    args = ap.parse_args()

    if args.once:
        run_once(args.telegram_token, args.chat_id, args.tone, args.threshold, args.interval)
    else:
        run_loop(args)


if __name__ == "__main__":
    main()
