#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram menu bot that calls export_json_unified.py and prints a friendly message.
Full file, paste as-is. Uses your existing tg_bot.tg_send for sending.
"""

import asyncio, json, os, subprocess, shlex
from datetime import datetime, timezone

# Your existing Telegram sender
from tg_bot import tg_send

DEFAULT_TF = 60
SPREAD = 1.2

HELP = (
"Send /menu then choose:\n"
"• FOREX → examples: EUR/USD, GBP/USD\n"
"• COMMODITY → XAU/USD, XAG/USD\n"
"• STOCKS → AAPL, TSLA, NVDA\n"
"Then pick timeframe."
)

def run_export(symbol, tf):
    cmd = f'python export_json_unified.py --symbol {shlex.quote(symbol)} --tf {int(tf)} --spread {SPREAD}'
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = p.stdout.strip() or p.stderr.strip()
    try:
        data = json.loads(out)
    except Exception:
        data = {"telegram_commentary":"Exporter failed.","risk_notes":[out[:200]]}
    return data

def render_human(title, data):
    lines = [f"📊 {title}", ""]
    if "price" in data:
        lines += [
            f"*Action*: `{data.get('pre_action','WAIT')}`",
            f"*Price*: `{data.get('price')}`",
            f"*Score16/6*: `{data.get('score16',0)}` / `{data.get('score6',0)}`",
        ]
    if data.get("why_short"):
        lines += ["— — — — —", "📌 *Why*:"]
        for w in data["why_short"]:
            lines.append(f"• {w}")
    if data.get("risk_notes"):
        lines += ["⚠️ *Risk*:"]
        for r in data["risk_notes"]:
            lines.append(f"• {r}")
    lines += ["", f"🕒 Built: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')}`"]
    return "\n".join(lines)

# -------------- simple asyncio poller --------------
async def main():
    # One-shot demo: send a few samples. Replace with your dispatcher if you already have one.
    samples = [
        ("FOREX / EURUSD / 1h",  "EUR/USD", 60),
        ("COMMODITY / XAUUSD / 1h", "XAU/USD", 60),
        ("STOCKS / TSLA / 5m", "TSLA", 5),
    ]
    for title, sym, tf in samples:
        data = run_export(sym, tf)
        msg = render_human(title, data)
        tg_send(msg, html=False)
    tg_send("Menu bot is online. Send /start (this demo just sent 3 samples).", html=False)

if __name__ == "__main__":
    asyncio.run(main())
