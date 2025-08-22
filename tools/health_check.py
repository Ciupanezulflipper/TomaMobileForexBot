#!/usr/bin/env python3
"""
Health check runner:
- Ensures project root is on sys.path
- Tries importing analyst from 'analyst' or 'modules.analyst'
- Prints env summary and attempts quick signals for EURUSD & XAUUSD
"""

import os, sys, importlib

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def try_import_analyst():
    candidates = ["analyst", "modules.analyst"]
    for mod in candidates:
        try:
            m = importlib.import_module(mod)
            return m
        except ModuleNotFoundError:
            continue
    return None

analyst_mod = try_import_analyst()
if not analyst_mod:
    print("[x] Could not import 'analyst' or 'modules.analyst'.")
    print("    Checked paths (first 3):", sys.path[:3])
    raise SystemExit(2)

# Functions are optional: we try to fetch them if present
make_signal = getattr(analyst_mod, "make_signal", None)
analyze_24h = getattr(analyst_mod, "analyze_24h", None)

def banner(t): print("\n" + "="*8, t, "="*8)

def env_summary():
    keys = [
        "TELEGRAM_BOT_TOKEN",
        "TWELVE_DATA_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "FINNHUB_KEY"
    ]
    banner("ENV SUMMARY")
    for k in keys:
        print(f"{k}: {'SET' if os.getenv(k) else 'MISSING'}")

def check_pair(pair: str) -> bool:
    if not make_signal:
        print(f"[warn] 'make_signal' not found in {analyst_mod.__name__}")
        return False
    try:
        s = make_signal(pair)
        print(f"{pair}: {s}")
        return True
    except Exception as e:
        print(f"[x] make_signal({pair}) failed:", e)
        return False

def main():
    env_summary()
    ok1 = check_pair("EURUSD")
    ok2 = check_pair("XAUUSD")
    if ok1 and ok2:
        print("\n[✓] Health check passed for EURUSD and XAUUSD.")
        raise SystemExit(0)
    else:
        print("\n[!] Health check encountered issues.")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
