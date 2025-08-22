#!/usr/bin/env python3
# export_json_td.py  —  TwelveData JSON exporter for Claude/Grok
#
# Produces JSON with:
# - symbol, timeframe, utc_build_time, price, spread_pips
# - technical_flags (16), fundamental_flags (6)
# - score16, score6, pre_action
#
# No external TA libs; light pandas math only.
# Timeframes supported: 5 (M5), 60 (H1), 240 (H4)

import os, sys, json, math, time, datetime as dt
import requests
import pandas as pd

# ---------- Config ----------
TD_KEY = os.getenv("TWELVE_DATA_API_KEY", "").strip()
if not TD_KEY:
    print(json.dumps({
        "action":"WAIT","score16":0,"score6":0,"why_short":[],
        "risk_notes":["Missing TWELVE_DATA_API_KEY"],"conflicts":[],
        "confidence_1to5":1,"telegram_commentary":"Missing API key."
    }))
    sys.exit(1)

# map minutes -> TwelveData interval label
TF_MAP = {5: "5min", 60: "1h", 240: "4h"}

def tf_label(tf_minutes:int)->str:
    return "M5" if tf_minutes==5 else ("H1" if tf_minutes==60 else ("H4" if tf_minutes==240 else f"{tf_minutes}m"))

def now_utc_iso()->str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"

def fetch_td(symbol:str, tf_minutes:int, limit:int=500)->pd.DataFrame:
    interval = TF_MAP.get(tf_minutes, "1h")
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": str(limit),
        "timezone": "UTC",
        "format": "JSON",
        "apikey": TD_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    values = (data or {}).get("values", [])
    if not values:
        raise RuntimeError(f"TwelveData empty for {symbol} {interval}: {data}")
    # newest first → reverse to ascending
    values = list(reversed(values))
    df = pd.DataFrame(values)
    # Ensure numeric dtypes
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime")
    df = df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    if df.empty:
        raise RuntimeError("No OHLCV rows after coercion.")
    return df

# --- Indicators (minimal) ---

def ema(s:pd.Series, n:int)->pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def rsi(s:pd.Series, n:int=14)->pd.Series:
    delta = s.diff()
    up = (delta.where(delta>0, 0)).rolling(n).mean()
    down = (-delta.where(delta<0, 0)).rolling(n).mean()
    rs = up/(down.replace(0, 1e-12))
    return 100 - (100/(1+rs))

def macd_line(s:pd.Series, fast=12, slow=26)->pd.Series:
    return ema(s, fast) - ema(s, slow)

def signal_line(macd:pd.Series, n=9)->pd.Series:
    return macd.ewm(span=n, adjust=False).mean()

def atr(df:pd.DataFrame, n:int=14)->pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def last_true(x:bool)->bool:
    return bool(x) if pd.notna(x) else False

def build_flags(df:pd.DataFrame)->dict:
    # compute indicators
    close = df["Close"]
    vol = df["Volume"]

    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    rsi14 = rsi(close, 14)

    macd = macd_line(close, 12, 26)
    sig = signal_line(macd, 9)

    atr14 = atr(df, 14)

    # momentum big body up/down (simple body vs range)
    body = (df["Close"] - df["Open"]).abs()
    rng = (df["High"] - df["Low"]).replace(0, 1e-12)
    big_body_up = (df["Close"] > df["Open"]) & ((body / rng) >= 0.6)
    big_body_dn = (df["Close"] < df["Open"]) & ((body / rng) >= 0.6)

    # simple engulfing
    prev_open = df["Open"].shift()
    prev_close = df["Close"].shift()
    bull_engulf = (df["Close"] > df["Open"]) & (prev_close < prev_open) & (df["Close"] >= prev_open) & (df["Open"] <= prev_close)
    bear_engulf = (df["Close"] < df["Open"]) & (prev_close > prev_open) & (df["Close"] <= prev_open) & (df["Open"] >= prev_close)

    # support/resistance break using rolling extremes
    roll = 20
    prev_max = df["High"].rolling(roll).max().shift()
    prev_min = df["Low"].rolling(roll).min().shift()
    sr_break_up = df["Close"] > prev_max
    sr_break_dn = df["Close"] < prev_min

    # high volume heuristic
    v_avg = vol.rolling(20).mean()
    high_volume = vol > (1.5 * v_avg)

    flags = {
        "ema9_gt_ema21":     last_true(ema9.iloc[-1] > ema21.iloc[-1]),
        "ema20_gt_ema50":    last_true(ema20.iloc[-1] > ema50.iloc[-1]),
        "rsi_gt_60":         last_true(rsi14.iloc[-1] > 60),
        "rsi_lt_40":         last_true(rsi14.iloc[-1] < 40),
        "macd_cross_up":     last_true(macd.iloc[-2] <= sig.iloc[-2]) and last_true(macd.iloc[-1] > sig.iloc[-1]),
        "macd_cross_down":   last_true(macd.iloc[-2] >= sig.iloc[-2]) and last_true(macd.iloc[-1] < sig.iloc[-1]),
        "adx_gt_20":         False,  # light exporter: skip ADX, keep false
        "above_200_ema":     last_true(close.iloc[-1] > ema200.iloc[-1]),
        "htf_confluence_up": False,  # single-TF exporter; keep false
        "htf_confluence_down": False,
        "momentum_big_body_up":   last_true(big_body_up.iloc[-1]),
        "momentum_big_body_down": last_true(big_body_dn.iloc[-1]),
        "sr_break_up":       last_true(sr_break_up.iloc[-1]),
        "sr_break_down":     last_true(sr_break_dn.iloc[-1]),
        "bearish_engulfing": last_true(bear_engulf.iloc[-1]),
        "bullish_engulfing": last_true(bull_engulf.iloc[-1]),
        # (that’s 16)
    }
    return flags

def build_fundamentals(spread_pips:float)->dict:
    # Placeholders that respect your 6-slot schema.
    # You can wire real feeds later (news/sentiment/etc).
    return {
        "no_red_news_1h": False,
        "news_sentiment_ok": False,
        "no_cb_conflict": False,
        "spread_ok": (spread_pips <= 2.0),
        "tg_agreement": False,
        "not_mid_candle": True,
    }

def choose_action(flags:dict)->str:
    bullish = [
        flags["ema9_gt_ema21"], flags["ema20_gt_ema50"], flags["rsi_gt_60"],
        flags["macd_cross_up"], flags["above_200_ema"], flags["momentum_big_body_up"],
        flags["sr_break_up"], flags["bullish_engulfing"]
    ]
    bearish = [
        flags["rsi_lt_40"], flags["macd_cross_down"], flags["momentum_big_body_down"],
        flags["sr_break_down"], flags["bearish_engulfing"]
    ]
    bull_votes = sum(1 for x in bullish if x)
    bear_votes = sum(1 for x in bearish if x)
    if bull_votes >= 3 and bear_votes == 0:
        return "BUY"
    if bear_votes >= 3 and bull_votes == 0:
        return "SELL"
    return "WAIT"

def build_payload(symbol:str, tf_minutes:int, spread_pips:float)->dict:
    df = fetch_td(symbol, tf_minutes, limit=500)

    # last price from last close; ensure positive, round nicely
    price = float(abs(df["Close"].iloc[-1]))

    # make sure spread is positive (your earlier output had a minus)
    spread = float(abs(spread_pips))

    tflags = build_flags(df)
    fflags = build_fundamentals(spread)

    score16 = sum(1 for v in tflags.values() if v)
    score6  = sum(1 for v in fflags.values() if v)
    pre_action = choose_action(tflags)

    payload = {
        "symbol": symbol,
        "timeframe": tf_label(tf_minutes),
        "utc_build_time": now_utc_iso(),
        "price": price,
        "spread_pips": spread,
        "score16": score16,
        "score6": score6,
        "pre_action": pre_action,
        "technical_flags": tflags,
        "technical_meta": {},   # reserved
        "fundamental_flags": fflags
    }
    return payload

def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="TwelveData JSON exporter")
    ap.add_argument("--symbol", required=True, help="e.g., EURUSD=X, USDJPY=X, XAUUSD=X")
    ap.add_argument("--tf", type=int, default=60, help="timeframe minutes (5,60,240)")
    ap.add_argument("--spread", type=float, default=1.2, help="spread in pips to include")
    return ap.parse_args()

def main():
    args = parse_args()
    try:
        payload = build_payload(args.symbol, args.tf, args.spread)
        print(json.dumps(payload, ensure_ascii=False, separators=(",",":")))
    except Exception as e:
        fallback = {
            "action":"WAIT","score16":0,"score6":0,"why_short":[],
            "risk_notes":[f"Exporter error: {str(e)}"],
            "conflicts":[], "confidence_1to5":1,
            "telegram_commentary":"Exporter failed to fetch/compute; check API key or rate limits."
        }
        print(json.dumps(fallback, ensure_ascii=False, separators=(",",":")))
        sys.exit(1)

if __name__ == "__main__":
    main()
