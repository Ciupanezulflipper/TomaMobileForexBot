# export_json.py — builds unified JSON for Claude/Grok (no bot send here)
# Full file. Self-contained. Uses yfinance only.
from __future__ import annotations
import os, json, math, argparse
from datetime import datetime, timezone, timedelta

import pandas as pd
import numpy as np

try:
    import yfinance as yf
except Exception as e:
    print(json.dumps({"error":"yfinance missing. pip install yfinance pandas numpy"}))
    raise

# -------- helpers --------
def now_utc_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def map_symbol_yf(s: str) -> str:
    s = s.upper().replace(" ", "")
    if "/" in s:
        base, quote = s.split("/",1)
        return f"{base}{quote}=X"
    if s.endswith("=X"): return s
    if len(s) in (6,7,8) and "=X" not in s:
        return f"{s}=X"
    return s

def tf_label(m: int) -> str:
    if m >= 1440: return "D1"
    if m >= 240: return "H4"
    if m >= 60: return "H1"
    if m >= 15: return "M15"
    return f"M{m}"

def fetch(yfsym: str, minutes: int, lookback_rows=400) -> pd.DataFrame:
    interval = "1h" if minutes==60 else ("4h" if minutes==240 else ("1d" if minutes>=1440 else f"{minutes}m"))
    period = "60d" if minutes <= 240 else "730d"
    df = yf.download(yfsym, interval=interval, period=period, progress=False, threads=False)
    if df is None or df.empty: return pd.DataFrame()
    df = df.rename(columns=str.title)
    df = df.dropna(subset=["Open","High","Low","Close"])
    if len(df) > lookback_rows: df = df.tail(lookback_rows)
    return df

# -------- indicators --------
def ema(s: pd.Series, n:int):
    return s.ewm(span=n, adjust=False).mean()

def rsi(series: pd.Series, n=14):
    delta = series.diff()
    up = (delta.clip(lower=0)).ewm(alpha=1/n, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / (down + 1e-12)
    return 100 - (100/(1+rs))

def macd(series: pd.Series, fast=12, slow=26, sig=9):
    ef = ema(series, fast)
    es = ema(series, slow)
    line = ef - es
    signal = ema(line, sig)
    hist = line - signal
    return line, signal, hist

def true_range(df):
    prev_c = df["Close"].shift(1)
    a = (df["High"]-df["Low"]).abs()
    b = (df["High"]-prev_c).abs()
    c = (df["Low"]-prev_c).abs()
    return pd.concat([a,b,c], axis=1).max(axis=1)

def atr(df, n=14):
    tr = true_range(df)
    return tr.rolling(n).mean()

def adx(df, n=14):
    up = df["High"].diff()
    dn = -df["Low"].diff()
    plus_dm = np.where((up>dn)&(up>0), up, 0.0)
    minus_dm = np.where((dn>up)&(dn>0), dn, 0.0)
    tr = true_range(df).rolling(n).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(n).mean() / (tr + 1e-12)
    minus_di= 100 * pd.Series(minus_dm,index=df.index).rolling(n).mean() / (tr + 1e-12)
    dx = ((plus_di - minus_di).abs() / ((plus_di + minus_di)+1e-12))*100
    return dx.rolling(n).mean()

# -------- patterns / utilities --------
def bull_engulf(df):
    if len(df)<2: return False
    p, c = df.iloc[-2], df.iloc[-1]
    return (p.Close < p.Open) and (c.Close > c.Open) and (c.Close > p.Open) and (c.Open < p.Close)

def bear_engulf(df):
    if len(df)<2: return False
    p, c = df.iloc[-2], df.iloc[-1]
    return (p.Close > p.Open) and (c.Close < c.Open) and (c.Close < p.Open) and (c.Open > p.Close)

def momentum_body_up(df):
    c = df.iloc[-1]
    body = abs(c.Close - c.Open)
    rng = (c.High - c.Low) + 1e-12
    return (c.Close > c.Open) and (body/rng >= 0.5)

def swing_levels(df, bars=120):
    seg = df.tail(min(bars, len(df)))
    return float(seg.High.max()), float(seg.Low.min())

def fib_touch(price, hi, lo, tol=0.003):
    if hi<=lo: return False
    diff = hi - lo
    f382 = lo + 0.382*diff
    f500 = lo + 0.5*diff
    f618 = lo + 0.618*diff
    for f in (f382, f500, f618):
        if abs(price - f)/max(1e-9, diff) <= tol:
            return True
    return False

def within_mid_guard(df, minutes:int, frac=0.15):
    # If last bar open time is close to now, avoid first/last 15%
    if len(df)<2: return True
    # yfinance index is tz-naive but UTC-ish; guard loosely
    # We’ll assume new bar forms every `minutes`
    return True  # keep simple & permissive for now

def spread_ok_default(symbol:str, spread_pips:float):
    # majors threshold: 1.5, others 2.0
    is_major = any(x in symbol for x in ["EURUSD","GBPUSD","USDJPY","AUDUSD","NZDUSD","USDCHF","USDCAD"])
    return spread_pips <= (1.5 if is_major else 2.0)

# -------- scoring & flags (16 + 6) --------
def build_flags(df_l: pd.DataFrame, df_h: pd.DataFrame, symbol:str, assumed_spread_pips:float):
    out = {
      "technical_flags": {
        "ema9_gt_ema21": False,
        "ema20_gt_ema50": False,
        "rsi_gt_60": False,
        "rsi_lt_40": False,
        "rsi_div": False,
        "macd_cross_up": False,
        "macd_cross_down": False,
        "macd_hist_flip": False,
        "adx_gt_20": False,
        "atr_zone": False,
        "candle_bull_engulf": False,
        "candle_bear_engulf": False,
        "mtf_confluence": False,
        "fibo_touch": False,
        "sr_break": False,
        "above_200_ema": False
      },
      "technical_meta": {
        "mtf_dir": "flat",
        "sr_dir": "none",
        "pattern_type": "none"
      },
      "fundamental_flags": {
        "no_red_news_1h": False,
        "news_sentiment_ok": False,
        "no_cb_conflict": False,
        "spread_ok": spread_ok_default(symbol, assumed_spread_pips),
        "tg_agreement": False,
        "not_mid_candle": within_mid_guard(df_l, 60)
      }
    }

    if df_l.empty: 
        return out, 0, 0

    close = df_l["Close"]
    ema9, ema21 = ema(close,9), ema(close,21)
    ema20, ema50 = ema(close,20), ema(close,50)
    ema200 = ema(close,200)
    r = rsi(close,14)
    macd_line, macd_sig, macd_hist = macd(close)
    adx_v = adx(df_l,14)
    atr_v = atr(df_l,14)

    # tech flags
    out["technical_flags"]["ema9_gt_ema21"] = bool(ema9.iloc[-1] > ema21.iloc[-1])
    out["technical_flags"]["ema20_gt_ema50"]= bool(ema20.iloc[-1] > ema50.iloc[-1])
    out["technical_flags"]["rsi_gt_60"]     = bool(r.iloc[-1] >= 60)
    out["technical_flags"]["rsi_lt_40"]     = bool(r.iloc[-1] <= 40)

    # very simple divergence proxy (use highs/lows vs RSI extremes)
    try:
        look=20
        s = close.tail(look); o=r.tail(look)
        ph = s.idxmax(); oh = o.idxmax()
        pl = s.idxmin(); ol = o.idxmin()
        bear = s.iloc[-1] >= s.loc[ph] and o.iloc[-1] < o.loc[oh]
        bull = s.iloc[-1] <= s.loc[pl] and o.iloc[-1] > o.loc[ol]
        out["technical_flags"]["rsi_div"] = bool(bear or bull)
    except Exception:
        out["technical_flags"]["rsi_div"] = False

    out["technical_flags"]["macd_cross_up"]   = bool(macd_line.iloc[-2] < macd_sig.iloc[-2] and macd_line.iloc[-1] > macd_sig.iloc[-1])
    out["technical_flags"]["macd_cross_down"] = bool(macd_line.iloc[-2] > macd_sig.iloc[-2] and macd_line.iloc[-1] < macd_sig.iloc[-1])
    out["technical_flags"]["macd_hist_flip"]  = bool((macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0) or (macd_hist.iloc[-1] < 0 and macd_hist.iloc[-2] >= 0))
    out["technical_flags"]["adx_gt_20"]       = bool(adx_v.iloc[-1] >= 20)

    out["technical_flags"]["atr_zone"]        = bool(atr_v.iloc[-1] >= atr_v.rolling(100).median().iloc[-1])

    be = bear_engulf(df_l); bu = bull_engulf(df_l)
    out["technical_flags"]["candle_bull_engulf"] = bool(bu)
    out["technical_flags"]["candle_bear_engulf"] = bool(be)
    if bu: out["technical_meta"]["pattern_type"] = "bull_engulf"
    if be: out["technical_meta"]["pattern_type"] = "bear_engulf"

    # MTF confluence: 21-EMA slope agrees
    if not df_h.empty and len(df_h)>2:
        e21_l = ema(df_l["Close"],21).diff().iloc[-1]
        e21_h = ema(df_h["Close"],21).diff().iloc[-1]
        if (e21_l>0 and e21_h>0): 
            out["technical_flags"]["mtf_confluence"]=True
            out["technical_meta"]["mtf_dir"]="up"
        elif (e21_l<0 and e21_h<0):
            out["technical_flags"]["mtf_confluence"]=True
            out["technical_meta"]["mtf_dir"]="down"
        else:
            out["technical_meta"]["mtf_dir"]="flat"

    hi, lo = swing_levels(df_l, 120)
    out["technical_flags"]["fibo_touch"] = bool(fib_touch(close.iloc[-1], hi, lo))

    # SR break
    sr_up = close.iloc[-1] > hi
    sr_dn = close.iloc[-1] < lo
    out["technical_flags"]["sr_break"] = bool(sr_up or sr_dn)
    out["technical_meta"]["sr_dir"] = "up" if sr_up else ("down" if sr_dn else "none")

    out["technical_flags"]["above_200_ema"] = bool(close.iloc[-1] >= ema200.iloc[-1])

    # scoring
    score16 = sum(1 for v in out["technical_flags"].values() if v)
    score6  = sum(1 for v in out["fundamental_flags"].values() if v)
    return out, score16, score6

def tentative_action(tech:dict) -> str:
    bulls = 0
    bears = 0
    # simple vote from key clusters
    if tech["ema9_gt_ema21"]: bulls+=1
    if tech["ema20_gt_ema50"]: bulls+=1
    if tech["rsi_gt_60"]: bulls+=1
    if tech["macd_cross_up"]: bulls+=1
    if tech["above_200_ema"]: bulls+=1
    if tech["mtf_confluence"]: bulls+=1 and False  # direction in meta

    if tech["rsi_lt_40"]: bears+=1
    if tech["macd_cross_down"]: bears+=1
    if tech["candle_bear_engulf"]: bears+=1
    # SR break direction sits in meta; we won’t count it here

    if bulls >=3 and bears==0: return "BUY"
    if bears >=3 and bulls==0: return "SELL"
    return "WAIT"

# -------- main --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="EURUSD, EUR/USD, USDJPY, XAUUSD, etc.")
    ap.add_argument("--tf", type=int, default=60, help="minutes; 60=H1, 240=H4")
    ap.add_argument("--spread", type=float, default=1.5, help="assumed spread in pips")
    args = ap.parse_args()

    ysym = map_symbol_yf(args.symbol)
    df_l = fetch(ysym, args.tf)
    df_h = fetch(ysym, 240) if args.tf != 240 else fetch(ysym, 60)  # use the other TF for confluence

    if df_l.empty:
        print(json.dumps({
            "symbol": args.symbol.upper().replace(" ","").replace("/",""),
            "timeframe": tf_label(args.tf),
            "utc_build_time": now_utc_iso(),
            "price": None,
            "spread_pips": args.spread,
            "score16": 0,
            "score6": 0,
            "pre_action": "WAIT",
            "technical_flags": {},
            "technical_meta": {},
            "fundamental_flags": {},
            "note": "No data"
        }, indent=2))
        return

    flags, s16, s6 = build_flags(df_l, df_h, args.symbol.upper(), args.spread)
    last_price = float(df_l["Close"].iloc[-1])
    action = tentative_action(flags["technical_flags"])

    payload = {
        "symbol": args.symbol.upper().replace(" ","").replace("/",""),
        "timeframe": tf_label(args.tf),
        "utc_build_time": now_utc_iso(),
        "price": last_price,
        "spread_pips": float(args.spread),
        "score16": int(s16),
        "score6": int(s6),
        "pre_action": action,
        "technical_flags": flags["technical_flags"],
        "technical_meta": flags["technical_meta"],
        "fundamental_flags": flags["fundamental_flags"]
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
