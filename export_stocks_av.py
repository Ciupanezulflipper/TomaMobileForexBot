#!/usr/bin/env python3
# export_stocks_av.py — standalone stock exporter (Alpha Vantage)
# Outputs unified JSON (symbol, timeframe, flags, scores, pre_action)
#
# Env needed: ALPHA_VANTAGE_API_KEY
# Usage:
#   python export_stocks_av.py --symbol TSLA --tf 5   > out.json
#   python export_stocks_av.py --symbol AAPL --tf 15  > out.json
#
import os, sys, json, argparse, datetime, math, time
from typing import Dict, Any, List

try:
    import requests
    import pandas as pd
except Exception as e:
    print(json.dumps({
        "action":"WAIT","score16":0,"score6":0,"why_short":[],
        "risk_notes":[f"dependency error: {type(e).__name__}: {e}"],
        "conflicts":[], "confidence_1to5":1,
        "telegram_commentary":"Exporter failed."
    })); sys.exit(0)

def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00","Z")

def av_timeframe(tf_minutes:int)->str:
    return {1:"1min",5:"5min",15:"15min",30:"30min",60:"60min"}.get(tf_minutes,"5min")

def fetch_av(symbol:str, tf_minutes:int, apikey:str)->pd.DataFrame:
    interval = av_timeframe(tf_minutes)
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol.upper().strip(),
        "interval": interval,
        "outputsize": "compact",
        "datatype": "json",
        "apikey": apikey
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    # Handle throttle note / error
    if "Time Series" not in str(data):
        raise RuntimeError(f"AlphaVantage response missing time series: {list(data.keys())[:3]}")
    # series key varies by interval, e.g. "Time Series (5min)"
    ts_key = [k for k in data.keys() if k.startswith("Time Series")][:1]
    if not ts_key: raise RuntimeError("Time Series key not found in AV response.")
    series = data[ts_key[0]]
    # Build DataFrame
    rows = []
    for ts, row in series.items():
        rows.append({
            "datetime": pd.to_datetime(ts, utc=True),
            "Open": float(row["1. open"]),
            "High": float(row["2. high"]),
            "Low": float(row["3. low"]),
            "Close": float(row["4. close"]),
            "Volume": float(row["5. volume"]),
        })
    if not rows: raise RuntimeError("No rows from Alpha Vantage.")
    df = pd.DataFrame(rows).sort_values("datetime").set_index("datetime")
    return df

def ema(series:pd.Series, n:int)->pd.Series:
    return series.ewm(span=n, adjust=False).mean()

def rsi(series:pd.Series, n:int=14)->pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1*delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/n, adjust=False).mean()
    ma_down = down.ewm(alpha=1/n, adjust=False).mean()
    rs = ma_up / (ma_down + 1e-12)
    return 100 - (100 / (1 + rs))

def macd(series:pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist

def last_macd_cross(macd_line:pd.Series, signal:pd.Series)->Dict[str,bool]:
    # Cross up if previous macd <= signal and current macd > signal
    if len(macd_line) < 2: return {"macd_cross_up":False, "macd_cross_down":False}
    m1, s1 = macd_line.iloc[-2], signal.iloc[-2]
    m2, s2 = macd_line.iloc[-1], signal.iloc[-1]
    up = (m1 <= s1) and (m2 > s2)
    down = (m1 >= s1) and (m2 < s2)
    return {"macd_cross_up": bool(up), "macd_cross_down": bool(down)}

def make_flags(df:pd.DataFrame)->Dict[str,bool]:
    close = df["Close"]
    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    rsi14 = rsi(close, 14)
    macd_line, signal, _ = macd(close)

    flags = {
        "ema9_gt_ema21": bool(ema9.iloc[-1] > ema21.iloc[-1]),
        "ema20_gt_ema50": bool(ema20.iloc[-1] > ema50.iloc[-1]),
        "rsi_gt_60": bool(rsi14.iloc[-1] > 60),
        "rsi_lt_40": bool(rsi14.iloc[-1] < 40),
        "above_200_ema": bool(close.iloc[-1] > ema200.iloc[-1]),
        "momentum_big_body_up": bool((close.iloc[-1] - df["Open"].iloc[-1]) / max(1e-9, df["Open"].iloc[-1]) > 0.004),
        "momentum_big_body_down": bool((df["Open"].iloc[-1] - close.iloc[-1]) / max(1e-9, df["Open"].iloc[-1]) > 0.004),
        "high_volume": bool(df["Volume"].iloc[-1] > df["Volume"].rolling(50).mean().iloc[-1]),
        "sr_break_up": False,
        "sr_break_down": False,
        "mtf_confluence_up": False,
        "mtf_confluence_down": False,
        "fibo_touch": False,
    }
    flags.update(last_macd_cross(macd_line, signal))
    return flags

def vote_action(flags:Dict[str,bool])->str:
    bull_keys = [
        "ema9_gt_ema21","ema20_gt_ema50","rsi_gt_60","macd_cross_up",
        "momentum_big_body_up","above_200_ema","high_volume"
    ]
    bear_keys = [
        "rsi_lt_40","macd_cross_down","momentum_big_body_down",
        "sr_break_down"
    ]
    bull = sum(1 for k in bull_keys if flags.get(k))
    bear = sum(1 for k in bear_keys if flags.get(k))
    if bull >= 3 and bull > bear: return "BUY"
    if bear >= 3 and bear > bull: return "SELL"
    return "WAIT"

def main():
    ap = argparse.ArgumentParser(description="Stock exporter via Alpha Vantage (intraday)")
    ap.add_argument("--symbol", required=True, help="e.g. TSLA, AAPL")
    ap.add_argument("--tf", type=int, default=5, help="minutes: 1,5,15,30,60")
    ap.add_argument("--spread", type=float, default=0.0, help="(optional) synthetic spread in pips")
    args = ap.parse_args()

    key = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY")
    if not key:
        print(json.dumps({
            "action":"WAIT","score16":0,"score6":0,"why_short":[],
            "risk_notes":["ALPHA_VANTAGE_API_KEY missing"],
            "conflicts":[], "confidence_1to5":1,
            "telegram_commentary":"Exporter failed: missing API key."
        })); sys.exit(0)

    try:
        df = fetch_av(args.symbol, args.tf, key)
        price = float(df["Close"].iloc[-1])
        flags = make_flags(df)
        score16 = int(sum(1 for v in flags.values() if v))
        # no fundamentals here; keep them benign/neutral
        fundamentals = {
            "no_red_news_1h": True,
            "news_sentiment_ok": True,
            "no_cb_conflict": True,
            "spread_ok": True,
            "tg_agreement": False,
            "not_mid_candle": True,
        }
        score6 = int(sum(1 for v in fundamentals.values() if v))
        pre_action = vote_action(flags)

        payload = {
            "symbol": args.symbol.upper(),
            "timeframe": f"M{args.tf}" if args.tf < 60 else f"H{args.tf//60}",
            "utc_build_time": utc_now_iso(),
            "price": price,
            "spread_pips": args.spread,
            "score16": score16,
            "score6": score6,
            "pre_action": pre_action,
            "technical_flags": flags,
            "technical_meta": {"src": "AV"},
            "fundamental_flags": fundamentals,
            "telegram_commentary": f"{pre_action} bias • bull={sum(1 for k,v in flags.items() if v and 'down' not in k)} / bear={sum(1 for k,v in flags.items() if v and ('down' in k or k=='rsi_lt_40'))} • src=AV"
        }
        print(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "action":"WAIT","score16":0,"score6":0,"why_short":[],
            "risk_notes":[f"Alpha Vantage error: {type(e).__name__}: {e}"],
            "conflicts":[], "confidence_1to5":1,
            "telegram_commentary":"Exporter failed; check API key or rate limits."
        }))
        sys.exit(0)

if __name__ == "__main__":
    main()
