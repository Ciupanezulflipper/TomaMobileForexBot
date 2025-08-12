"""
market_data_fetcher.py
Robust, Termux-friendly data fetcher that ALWAYS returns:
{
  "pair": "<SYMBOL or NAME>",
  "score": <float 0..1>,
  "bias": "bullish|bearish|neutral",
  "levels": {"support":[...], "resistance":[...]},
  "reason": "<string>"
}

Data source: yfinance (pinned 0.2.40 to avoid curl_cffi on Termux).
If data is missing/unavailable, returns a neutral fallback.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- Symbols we support ----------
FOREX: Dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "USDCAD": "USDCAD=X",
    "EURGBP": "EURGBP=X",
}

COMMODITIES: Dict[str, str] = {
    "XAUUSD": "GC=F",   # Gold (COMEX)
    "XAGUSD": "SI=F",   # Silver (COMEX)
    "WTI":    "CL=F",   # WTI Crude
    "BRENT":  "BZ=F",   # Brent Crude
    "NGAS":   "NG=F",   # Natural Gas
}

ALL_MAP: Dict[str, str] = {**FOREX, **COMMODITIES}


# ---------- Helpers ----------
def _fallback(pair: str, why: str) -> Dict:
    return {
        "pair": pair.upper(),
        "score": 0.50,
        "bias": "neutral",
        "levels": {"support": [], "resistance": []},
        "reason": f"No data from provider; neutral fallback. {why}".strip(),
    }


def _pct_to_score(pct_change: float) -> Tuple[float, str, str]:
    """
    Map +/-5% range into 0..1; aside of that it clamps.
    Bias band: > +1% bullish, < -1% bearish, else neutral.
    """
    score = (pct_change + 5.0) / 10.0
    score = max(0.0, min(1.0, score))
    if pct_change > 1.0:
        return score, "bullish", f"Price +{pct_change:.2f}% in last 24h."
    if pct_change < -1.0:
        return score, "bearish", f"Price {pct_change:.2f}% in last 24h."
    return score, "neutral", "Price within ±1% in last 24h."


def _levels_from_ohlc(df: pd.DataFrame, n: int = 3) -> Dict[str, List[float]]:
    try:
        # Use last 48 hourly bars if available
        recent = df.tail(48)
        lows = recent["Low"].dropna().sort_values().head(n).round(5).tolist()
        highs = recent["High"].dropna().sort_values(ascending=True).tail(n).round(5).tolist()
        highs.sort(reverse=True)
        return {"support": lows, "resistance": highs}
    except Exception as e:
        log.warning("levels calc failed: %s", e)
        return {"support": [], "resistance": []}


def _history_retry(ticker: str, period: str, interval: str, tries: int = 3) -> pd.DataFrame:
    last_exc = None
    for k in range(tries):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception as e:
            last_exc = e
            time.sleep(1.2 * (k + 1))
    if last_exc:
        log.warning("history failed for %s: %s", ticker, last_exc)
    return pd.DataFrame()


# ---------- Public API ----------
def analyze_24h(symbol_or_name: str) -> Dict:
    """
    Main entrypoint. Accepts 'EURUSD', 'EURUSD=X', 'XAUUSD', 'WTI', etc.
    Always returns a complete dict (never missing 'score').
    """
    s = symbol_or_name.upper().replace("/", "").strip()

    # Resolve to a yfinance ticker
    if s in ALL_MAP:
        ysym = ALL_MAP[s]
        pair_label = s
    elif s in ALL_MAP.values():
        ysym = s
        # try to find pretty label
        rev = {v: k for k, v in ALL_MAP.items()}
        pair_label = rev.get(s, s)
    else:
        # Try a few common normalizations (EURUSD=X)
        ysym = s if s.endswith("=X") or s.endswith("=F") else f"{s}=X"
        pair_label = s

    # Fetch 2 days of hourly bars; then isolate last 24h window
    df = _history_retry(ysym, period="2d", interval="1h", tries=3)
    if df.empty or "Close" not in df.columns:
        return _fallback(pair_label, "Empty DataFrame.")

    # Ensure timezone-aware index for slicing
    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
    end = df.index[-1]
    start = end - timedelta(days=1)
    last24 = df.loc[df.index >= start]

    if last24.empty or len(last24) < 2:
        # fallback to whatever we have
        last24 = df.tail(24)
        if last24.empty or len(last24) < 2:
            return _fallback(pair_label, "Insufficient bars.")

    try:
        first_close = float(last24["Close"].iloc[0])
        last_close = float(last24["Close"].iloc[-1])
        if first_close == 0 or not np.isfinite(first_close) or not np.isfinite(last_close):
            return _fallback(pair_label, "Invalid close values.")
        pct = (last_close / first_close - 1.0) * 100.0
    except Exception as e:
        return _fallback(pair_label, f"Change calc error: {e}")

    score, bias, reason = _pct_to_score(pct)
    levels = _levels_from_ohlc(last24)

    return {
        "pair": pair_label,
        "score": float(score),
        "bias": bias,
        "levels": levels,
        "reason": reason,
    }


# Quick self-test (optional)
if __name__ == "__main__":
    tests = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "WTI", "BRENT"]
    for t in tests:
        r = analyze_24h(t)
        print(f"{t:7s} -> score={r['score']:.2f} bias={r['bias']:7s} levels={len(r['levels']['support'])}/{len(r['levels']['resistance'])} | {r['reason']}")
