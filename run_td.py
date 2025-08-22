#!/usr/bin/env python3
# TomaMobileForexBot runner (TwelveData + core analyzer)
# EOF replacement (no patches)

import sys, os, importlib, argparse, json
from datetime import datetime, timezone

# Ensure current dir is importable
ROOT = os.path.abspath(os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Telegram (optional)
try:
    from tg_bot import tg_send
except Exception:
    tg_send = None

# Try to import the renderer module if you have one; else use fallback below
def render_basic(res: dict) -> str:
    sym   = res.get("symbol", "?")
    tf    = res.get("tf_lbl", "?")
    src   = res.get("src", "TD")
    price = res.get("price", "?")

    s16 = int(res.get("score16", 0))
    s6  = int(res.get("score6", 0))
    flags16 = res.get("flags16", {})
    flags6  = res.get("flags6", {})

    action = res.get("action", "WAIT")
    why_lst = res.get("why", []) or []

    built = res.get("built_utc") or datetime.now(timezone.utc).isoformat()

    # Pretty format
    lines = []
    lines.append(f"🧭 #{sym.replace('/','')}")
    lines.append(f"*{sym}* — *{action}* (Score {s16}/16 + {s6}/6) | TF *{tf}*")
    lines.append("")
    lines.append(f"🕰 Timeframe: *{tf}* | Source: `{src}`")
    lines.append("")
    lines.append(f"💰 Price: `{price}`")
    lines.append(f"🇮🇹 Score16/6: `{s16}` / `{s6}`")
    lines.append("— — — — — — —")
    lines.append("📌 *Why (rules)*:")
    if why_lst:
        for w in why_lst:
            lines.append(f"• {w}")
    else:
        lines.append("⚠️ Analyzer missing; sent minimal output from candles.")

    lines.append("")
    lines.append(f"🕒 Built: `{built}`")
    return "\n".join(lines)

def analyze_shim(core_mod, symbol: str, tf_minutes: int) -> dict:
    """
    Minimal fallback only if core.analyze_once truly missing.
    """
    try:
        df, src, tf_lbl = core_mod.get_candles(symbol, tf_minutes)
        price = float(df["Close"].iloc[-1]) if len(df) else "n/a"
    except Exception as e:
        df, src, tf_lbl, price = None, "TD", f"{tf_minutes}m", "n/a"

    return {
        "symbol": symbol,
        "tf_lbl": tf_lbl,
        "src": src,
        "price": price,
        "score16": 0,
        "flags16": {},
        "score6": 0,
        "flags6": {},
        "action": "WAIT",
        "why": ["Analyzer missing; using fallback."],
        "built_utc": datetime.now(timezone.utc).isoformat()
    }

def main():
    ap = argparse.ArgumentParser(description="TomaMobileForexBot runner")
    ap.add_argument("symbol", help='e.g. "EUR/USD"')
    ap.add_argument("tf", type=int, help="timeframe minutes, e.g. 5, 60, 240")
    ap.add_argument("--send", action="store_true", help="send to Telegram")
    args = ap.parse_args()

    # Import core and show exactly which file we got
    core = importlib.import_module("core")
    print(f"[debug] core.__file__ = {getattr(core, '__file__', None)}")
    print(f"[debug] has analyze_once: {hasattr(core, 'analyze_once')}, has get_candles: {hasattr(core, 'get_candles')}")

    # Choose analyzer (prefer real analyzer)
    if hasattr(core, "analyze_once"):
        res = core.analyze_once(args.symbol, args.tf)
        # Guard: if analyzer returned None/Falsey, fallback (shouldn't happen)
        if not res:
            print("[warn] analyze_once returned empty result; falling back to shim.")
            res = analyze_shim(core, args.symbol, args.tf)
    else:
        print("[warn] core.analyze_once not present; using shim.")
        res = analyze_shim(core, args.symbol, args.tf)

    # Choose renderer
    try:
        render_mod = importlib.import_module("render")
        msg = render_mod.render(res)  # your custom renderer if present
    except Exception:
        msg = render_basic(res)

    # Always print to stdout
    print(msg)

    # Optional Telegram
    if args.send:
        if tg_send is None:
            print("⚠️ Telegram sender not available (tg_bot.py missing?).")
        else:
            if len(msg) > 3800:
                tg_send(msg, as_file=True, filename="signal.txt")
                tg_send("📎 Signal too long, attached as file", html=False)
            else:
                tg_send(msg, html=False)  # markdown-like asterisks

if __name__ == "__main__":
    main()
