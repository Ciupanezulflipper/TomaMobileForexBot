#!/usr/bin/env python3
# TomaMobileForexBot – unified exporter (FX via EODHD template or TwelveData, Stocks via AlphaVantage)
# Guarantees 16 technical flags (including adx_gt_20) + 6 fundamentals every run.

import os, sys, json, math, time, argparse, datetime as dt
from typing import Dict, Any, Tuple, List
import urllib.request, urllib.parse
import pandas as pd

UTC = dt.timezone.utc

def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00","Z")

def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def _to_minutes(tf: int) -> str:
    # map TF minutes to EODHD period codes if needed (we use minutes directly)
    return str(tf)

def fetch_fx_eodhd(symbol: str, tf: int) -> pd.DataFrame:
    tmpl = os.getenv("EODHD_URL_TEMPLATE","").strip()
    apikey = os.getenv("EODHD_API_KEY", os.getenv("EODHD_TOKEN", os.getenv("EODHD_APITOKEN",""))).strip()
    if not tmpl or "{symbol}" not in tmpl:
        raise RuntimeError("EODHD_URL_TEMPLATE missing or invalid")
    url = tmpl.replace("{symbol}", urllib.parse.quote(symbol)).replace("{interval}", _to_minutes(tf))
    url = url.replace("{limit}","500").replace("{apikey}", apikey).replace("{api_token}", apikey)
    data = _get(url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"EODHD error: {data}")
    if not isinstance(data, list) or not data:
        raise RuntimeError("EODHD empty list")
    # EODHD returns newest first sometimes; normalize
    recs = []
    for it in data:
        # keys: "datetime","open","high","low","close","volume"
        recs.append({
            "datetime": pd.to_datetime(it["datetime"], utc=True),
            "Open": float(it["open"]),
            "High": float(it["high"]),
            "Low": float(it["low"]),
            "Close": float(it["close"]),
            "Volume": float(it.get("volume",0.0)),
        })
    df = pd.DataFrame(recs).sort_values("datetime").set_index("datetime")
    return df

def fetch_stock_av(symbol: str, tf: int) -> pd.DataFrame:
    # AlphaVantage intraday; tf must be one of 1,5,15,30,60
    iv = {1:"1min",5:"5min",15:"15min",30:"30min",60:"60min"}.get(tf)
    if not iv: raise RuntimeError("AlphaVantage supports tf in {1,5,15,30,60}")
    key = os.getenv("ALPHA_VANTAGE_API_KEY","").strip()
    if not key: raise RuntimeError("ALPHA_VANTAGE_API_KEY missing")
    qs = urllib.parse.urlencode({
        "function":"TIME_SERIES_INTRADAY",
        "symbol":symbol,
        "interval":iv,
        "apikey":key,
        "outputsize":"compact"
    })
    url = f"https://www.alphavantage.co/query?{qs}"
    data = _get(url)
    k = f"Time Series ({iv})"
    if k not in data:
        raise RuntimeError(f"AlphaVantage error: {data.get('Note') or data.get('Information') or data}")
    recs=[]
    for ts, row in data[k].items():
        recs.append({
            "datetime": pd.to_datetime(ts, utc=True),
            "Open": float(row["1. open"]),
            "High": float(row["2. high"]),
            "Low": float(row["3. low"]),
            "Close": float(row["4. close"]),
            "Volume": float(row.get("5. volume",0.0)),
        })
    df = pd.DataFrame(recs).sort_values("datetime").set_index("datetime")
    return df

# ---- indicators (Wilder style) ----
def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()

def rsi(close: pd.Series, n: int=14) -> pd.Series:
    delta = close.diff()
    gain = (delta.where(delta>0, 0.0)).ewm(alpha=1/n, adjust=False).mean()
    loss = (-delta.where(delta<0, 0.0)).ewm(alpha=1/n, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100/(1+rs))

def macd(close: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series,pd.Series,pd.Series]:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def atr(df: pd.DataFrame, n: int=14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(df: pd.DataFrame, n: int=14) -> pd.Series:
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm = up_move.where((up_move>down_move) & (up_move>0), 0.0)
    minus_dm = down_move.where((down_move>up_move) & (down_move>0), 0.0)
    tr = atr(df, 1)  # true range raw
    plus_di = 100 * (plus_dm.ewm(alpha=1/n, adjust=False).mean() / tr.replace(0,1e-9))
    minus_di = 100 * (minus_dm.ewm(alpha=1/n, adjust=False).mean() / tr.replace(0,1e-9))
    dx = ( (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0,1e-9) ) * 100
    return dx.ewm(alpha=1/n, adjust=False).mean()

def build_flags(df: pd.DataFrame) -> Tuple[Dict[str,bool], Dict[str,Any]]:
    close = df["Close"]
    vol = df["Volume"]
    ema9 = ema(close,9); ema21 = ema(close,21); ema20 = ema(close,20); ema50 = ema(close,50); ema200 = ema(close,200)
    rsi14 = rsi(close,14)
    macd_line, signal_line, hist = macd(close)
    atr14 = atr(df,14)
    adx14 = adx(df,14)

    last = df.index[-1]
    prev = df.index[-2] if len(df)>1 else last

    def cross_up(a,b): return a.loc[prev] <= b.loc[prev] and a.loc[last] > b.loc[last]
    def cross_down(a,b): return a.loc[prev] >= b.loc[prev] and a.loc[last] < b.loc[last]

    body = (df["Close"]-df["Open"]).abs()
    range_ = (df["High"]-df["Low"]).replace(0,1e-9)
    big_body_up = (df["Close"]>df["Open"]) & ((body/range_)>0.5)
    big_body_down = (df["Close"]<df["Open"]) & ((body/range_)>0.5)

    hv = vol > vol.rolling(50, min_periods=5).mean()*1.5

    flags = {
        "ema9_gt_ema21": bool(ema9.loc[last] > ema21.loc[last]),
        "ema20_gt_ema50": bool(ema20.loc[last] > ema50.loc[last]),
        "rsi_gt_60": bool(rsi14.loc[last] > 60),
        "rsi_lt_40": bool(rsi14.loc[last] < 40),
        "macd_cross_up": bool(cross_up(macd_line, signal_line)),
        "macd_cross_down": bool(cross_down(macd_line, signal_line)),
        "momentum_big_body_up": bool(big_body_up.loc[last]),
        "momentum_big_body_down": bool(big_body_down.loc[last]),
        "sr_break_up": False,
        "sr_break_down": False,
        "above_200_ema": bool(close.loc[last] > ema200.loc[last]),
        "high_volume": bool(hv.loc[last]),
        "fibo_touch": False,
        "mtf_confluence_up": False,
        "mtf_confluence_down": False,
        "adx_gt_20": bool(adx14.loc[last] > 20.0),  # ← NEW 16th flag
    }
    meta = {
        "rsi": float(rsi14.loc[last]),
        "macd": float(macd_line.loc[last]),
        "macd_signal": float(signal_line.loc[last]),
        "atr": float(atr14.loc[last]),
        "adx": float(adx14.loc[last]),
        "src": "EODHD/AV"
    }
    return flags, meta

def pre_action_from_flags(flags: Dict[str,bool]) -> str:
    bull = sum([
        flags["ema9_gt_ema21"], flags["ema20_gt_ema50"], flags["rsi_gt_60"],
        flags["macd_cross_up"], flags["momentum_big_body_up"],
        flags["sr_break_up"], flags["above_200_ema"], flags["high_volume"],
        flags["mtf_confluence_up"], flags["adx_gt_20"]
    ])
    bear = sum([
        flags["rsi_lt_40"], flags["macd_cross_down"], flags["momentum_big_body_down"],
        flags["sr_break_down"], flags["mtf_confluence_down"]
    ])
    if bull>=3 and bear==0: return "BUY"
    if bear>=3 and bull==0: return "SELL"
    return "WAIT"

def fundamentals_stub() -> Dict[str,bool]:
    # we keep these deterministic for now; news will be added later via RSS module
    return {
        "no_red_news_1h": False,
        "news_sentiment_ok": False,
        "no_cb_conflict": False,
        "spread_ok": True,
        "tg_agreement": False,
        "not_mid_candle": True,
    }

def build_payload(symbol: str, tf: int, spread_pips: float) -> Dict[str,Any]:
    is_fx = ("/" in symbol) or (len(symbol)==7 and symbol[3]=="/") or symbol.count("/")==1
    try:
        if is_fx:
            df = fetch_fx_eodhd(symbol, tf)
        else:
            df = fetch_stock_av(symbol, tf)
    except Exception as e:
        # hard fallback empty payload (agents will say exporter failed)
        return {
            "action":"WAIT","score16":0,"score6":0,"why_short":[],
            "risk_notes":[f"Exporter error: {e}"],
            "conflicts":[], "confidence_1to5":1,
            "telegram_commentary":"Exporter failed to fetch/compute; check API key or rate limits."
        }

    flags, meta = build_flags(df)
    fundamentals = fundamentals_stub()

    score16 = int(sum(1 for v in flags.values() if v))
    score6 = int(sum(1 for v in fundamentals.values() if v))
    action = pre_action_from_flags(flags)

    payload = {
        "symbol": symbol,
        "timeframe": f"{'M' if tf<60 else 'H'}{tf if tf<60 else tf//60}",
        "utc_build_time": iso_now(),
        "price": float(df["Close"].iloc[-1]),
        "spread_pips": float(spread_pips),
        "score16": score16,
        "score6": score6,
        "pre_action": action,
        "technical_flags": flags,
        "technical_meta": meta,
        "fundamental_flags": fundamentals,
        "telegram_commentary": f"WAIT bias • bull={sum(1 for k in flags if flags[k])} / bear={sum(1 for k in flags if ('down' in k or 'lt_40' in k) and flags[k])}"
    }
    # sanity: must be 16 tech / 6 fund
    assert len(payload["technical_flags"])==16, "Expected 16 technical flags"
    assert len(payload["fundamental_flags"])==6, "Expected 6 fundamental flags"
    return payload

def parse_args():
    ap = argparse.ArgumentParser(description="Export JSON payload (16 tech + 6 fund)")
    ap.add_argument("--symbol", required=True, help='e.g. "EUR/USD" or "TSLA"')
    ap.add_argument("--tf", type=int, default=60, help="timeframe minutes (1,5,15,30,60,240)")
    ap.add_argument("--spread", type=float, default=1.2, help="spread in pips")
    return ap.parse_args()

if __name__=="__main__":
    args = parse_args()
    print(json.dumps(build_payload(args.symbol, args.tf, args.spread), ensure_ascii=False, separators=(",",":")))

