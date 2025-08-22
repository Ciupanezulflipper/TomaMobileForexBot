#!/usr/bin/env python3
import os, sys, argparse, json, math, datetime as dt
from typing import Tuple, Dict, Any, List
import requests
import pandas as pd

# ---------- Config / Env ----------
# We will look for your Alpha Vantage key under any of these names:
AV_ENV_KEYS = [
    "ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY",
    "ALPHA_VANTAGE_KEY", "AV_API_KEY", "ALPHAVANTAGE_KEY"
]

def get_av_key() -> str:
    for k in AV_ENV_KEYS:
        v = os.getenv(k)
        if v:
            return v.strip()
    raise RuntimeError(
        f"Alpha Vantage API key not found. Set one of: {', '.join(AV_ENV_KEYS)}"
    )

# ---------- Symbol helpers ----------
def normalize_pair(sym: str) -> Tuple[str, str, str]:
    """
    Accepts: 'EURUSD', 'EUR/USD', 'EURUSD=X', 'USDJPY', 'USD/JPY'
    Returns: (from_symbol, to_symbol, nice_symbol)
    """
    s = sym.upper().replace("=X", "").replace("-", "").replace(" ", "")
    s = s.replace("/", "")
    if len(s) not in (6, 7):  # 6 normal, allow 'XAUUSD' length 6 too
        # try to guess simple cases
        pass
    if len(s) >= 6:
        fs, ts = s[:3], s[3:6]
        return fs, ts, f"{fs}{ts}"
    raise ValueError(f"Unrecognized symbol format: {sym}")

def tf_minutes_to_label(tf_minutes: int) -> str:
    if tf_minutes == 5: return "M5"
    if tf_minutes == 15: return "M15"
    if tf_minutes == 30: return "M30"
    if tf_minutes == 60: return "H1"
    if tf_minutes == 240: return "H4"
    return f"{tf_minutes}m"

def interval_for_av(tf_minutes: int) -> str:
    # Alpha Vantage intraday allowed: 1min, 5min, 15min, 30min, 60min
    m = {1:"1min",5:"5min",15:"15min",30:"30min",60:"60min"}
    if tf_minutes not in m:
        raise ValueError("Alpha Vantage FX_INTRADAY supports 1,5,15,30,60 minutes only")
    return m[tf_minutes]

# ---------- Fetch FX candles from Alpha Vantage ----------
def fetch_fx_intraday(from_sym: str, to_sym: str, tf_minutes: int, api_key: str) -> pd.DataFrame:
    interval = interval_for_av(tf_minutes)
    url = (
        "https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY&from_symbol={from_sym}"
        f"&to_symbol={to_sym}&interval={interval}&outputsize=compact&apikey={api_key}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    key = f"Time Series FX ({interval})"
    if key not in data:
        raise RuntimeError(f"Alpha Vantage error/limit: {data.get('Note') or data.get('Error Message') or str(data)[:200]}")
    # Build DataFrame
    ts = data[key]
    rows = []
    for t, ohlc in ts.items():
        rows.append({
            "datetime": pd.to_datetime(t, utc=True),
            "Open": float(ohlc["1. open"]),
            "High": float(ohlc["2. high"]),
            "Low": float(ohlc["3. low"]),
            "Close": float(ohlc["4. close"]),
            "Volume": 0.0,  # AV FX doesn't provide volume
        })
    df = pd.DataFrame(rows).sort_values("datetime").set_index("datetime")
    return df

# ---------- Simple TA helpers (lightweight, no TA-Lib) ----------
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1/length, adjust=False).mean()
    roll_down = down.ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / (roll_down.replace(0, 1e-12))
    return 100 - (100 / (1 + rs))

def bullish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2: return False
    prev = df.iloc[-2]
    cur = df.iloc[-1]
    prev_body_down = prev["Close"] < prev["Open"]
    cur_body_up = cur["Close"] > cur["Open"]
    return prev_body_down and cur_body_up and (cur["Close"] > prev["Open"]) and (cur["Open"] < prev["Close"])

def bearish_engulfing(df: pd.DataFrame) -> bool:
    if len(df) < 2: return False
    prev = df.iloc[-2]
    cur = df.iloc[-1]
    prev_body_up = prev["Close"] > prev["Open"]
    cur_body_down = cur["Close"] < cur["Open"]
    return prev_body_up and cur_body_down and (cur["Open"] > prev["Close"]) and (cur["Close"] < prev["Open"])

def big_body_up(df: pd.DataFrame) -> bool:
    if len(df) < 1: return False
    c = df.iloc[-1]
    rng = c["High"] - c["Low"]
    body = abs(c["Close"] - c["Open"])
    if rng <= 0: return False
    return (c["Close"] > c["Open"]) and (body / rng > 0.6)

def big_body_down(df: pd.DataFrame) -> bool:
    if len(df) < 1: return False
    c = df.iloc[-1]
    rng = c["High"] - c["Low"]
    body = abs(c["Close"] - c["Open"])
    if rng <= 0: return False
    return (c["Close"] < c["Open"]) and (body / rng > 0.6)

# ---------- Build 16 tech + 6 fund flags (simple) ----------
def compute_flags(df: pd.DataFrame) -> Dict[str, bool]:
    out = {}
    close = df["Close"]
    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    r = rsi(close, 14)

    out["ema9_gt_ema21"] = bool(ema9.iloc[-1] > ema21.iloc[-1])
    out["ema20_gt_ema50"] = bool(ema20.iloc[-1] > ema50.iloc[-1])
    out["rsi_gt_60"] = bool(r.iloc[-1] > 60)
    out["rsi_lt_40"] = bool(r.iloc[-1] < 40)
    # placeholders we can’t compute precisely without more libs:
    out["macd_cross_up"] = False
    out["macd_cross_down"] = False
    out["adx_gt_20"] = False
    out["above_200_ema"] = bool(close.iloc[-1] > ema200.iloc[-1])
    out["htf_confluence_up"] = False
    out["htf_confluence_down"] = False
    out["momentum_big_body_up"] = big_body_up(df)
    out["momentum_big_body_down"] = big_body_down(df)
    out["sr_break_up"] = False
    out["sr_break_down"] = False
    out["bearish_engulfing"] = bearish_engulfing(df)
    out["bullish_engulfing"] = bullish_engulfing(df)

    # ensure exactly 16 keys:
    assert len(out) == 16, f"tech flags count != 16 (got {len(out)})"
    return out

def compute_fund_flags() -> Dict[str, bool]:
    # We don’t fetch news here; keep simple and explicit:
    return {
        "no_red_news_1h": False,
        "news_sentiment_ok": False,
        "no_cb_conflict": True,     # assume OK by default
        "spread_ok": True,          # assume OK; caller passes spread number
        "tg_agreement": True,       # operator agrees to signal wording
        "not_mid_candle": True,     # assume we trigger near bar close
    }

def pre_action_from_flags(tech: Dict[str, bool]) -> str:
    bullish = sum([
        tech["ema9_gt_ema21"],
        tech["ema20_gt_ema50"],
        tech["rsi_gt_60"],
        tech["above_200_ema"],
        tech["momentum_big_body_up"],
        tech["bullish_engulfing"],
        tech["sr_break_up"],
        tech["htf_confluence_up"],
    ])
    bearish = sum([
        tech["rsi_lt_40"],
        tech["momentum_big_body_down"],
        tech["bearish_engulfing"],
        tech["sr_break_down"],
        tech["htf_confluence_down"],
        tech["macd_cross_down"],
        not tech["above_200_ema"],
        not tech["ema9_gt_ema21"],
    ])
    if bullish >= 3 and bearish == 0:
        return "BUY"
    if bearish >= 3 and bullish == 0:
        return "SELL"
    return "WAIT"

# ---------- Main export ----------
def build_payload(symbol_in: str, tf_minutes: int, spread_pips: float) -> Dict[str, Any]:
    api_key = get_av_key()
    fs, ts, nice = normalize_pair(symbol_in)
    df = fetch_fx_intraday(fs, ts, tf_minutes, api_key)
    if len(df) == 0:
        raise RuntimeError("No candles returned from Alpha Vantage.")

    tech = compute_flags(df)
    fund = compute_fund_flags()
    price = float(df["Close"].iloc[-1])

    # scores:
    score16 = int(sum(1 for v in tech.values() if v))
    score6 = int(sum(1 for v in fund.values() if v))

    payload = {
        "symbol": nice,
        "timeframe": tf_minutes_to_label(tf_minutes),
        "utc_build_time": dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "price": price,
        "spread_pips": float(spread_pips),
        "score16": score16,
        "score6": score6,
        "pre_action": pre_action_from_flags(tech),
        "technical_flags": tech,
        "technical_meta": {"bars": len(df)},
        "fundamental_flags": fund,
        "note": "from Alpha Vantage FX_INTRADAY",
    }
    return payload

def main():
    ap = argparse.ArgumentParser(description="Export JSON for Claude/Grok (Alpha Vantage FX)")
    ap.add_argument("--symbol", required=True, help="e.g. EURUSD, EUR/USD, USDJPY")
    ap.add_argument("--tf", type=int, default=60, help="timeframe minutes (1,5,15,30,60)")
    ap.add_argument("--spread", type=float, default=1.2, help="spread in pips to include")
    args = ap.parse_args()
    try:
        payload = build_payload(args.symbol, args.tf, args.spread)
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ": ")))
    except Exception as e:
        # Always produce *some* JSON so your Claude/Grok flow doesn't break
        fallback = {
            "action": "WAIT",
            "score16": 0,
            "score6": 0,
            "why_short": [],
            "risk_notes": [f"Exporter error: {str(e)}"],
            "conflicts": [],
            "confidence_1to5": 1,
            "telegram_commentary": "Exporter failed to fetch/compute; check API key or rate limits."
        }
        print(json.dumps(fallback, ensure_ascii=False, separators=(",", ": ")))
        sys.exit(1)

if __name__ == "__main__":
    main()
