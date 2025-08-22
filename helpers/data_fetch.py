import os, requests, datetime as dt
from typing import List, Tuple

BASE = "https://api.twelvedata.com/time_series"
# tf (minutes) -> TwelveData interval
TF_MAP = {5:"5min", 60:"1h", 240:"4h"}

def _map_symbol(sym:str)->str:
    """
    Normalize symbol into TwelveData format.
    Accepts 'EUR/USD' or 'EURUSD' or 'EURUSD=X' and returns 'EUR/USD'.
    """
    s = sym.upper().replace("=X","").replace("_","").replace(" ","")
    if "/" not in s:
        # try to insert slash for 6-char forex pairs
        if len(s)==6: s = s[:3] + "/" + s[3:]
    return s

def fetch_candles(symbol:str, tf:int, limit:int=400) -> Tuple[List[float], List[float], List[float], List[float], List[str]]:
    """
    Returns (opens, highs, lows, closes, times_utc_iso).
    Raises RuntimeError with a clear message if something is wrong.
    """
    api_key = os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVEDATA_KEY")
    if not api_key:
        raise RuntimeError("TWELVE_DATA_API_KEY not set in environment/.env")

    interval = TF_MAP.get(tf)
    if not interval:
        raise RuntimeError(f"Unsupported timeframe {tf}. Use one of {sorted(TF_MAP.keys())}")

    sym = _map_symbol(symbol)
    params = {
        "symbol": sym,
        "interval": interval,
        "outputsize": str(limit),
        "format": "JSON",
        "apikey": api_key,
        # optional: get consistent UTC ISO stamps
        "timezone": "UTC",
        "order": "ASC",
    }
    r = requests.get(BASE, params=params, timeout=12)
    if r.status_code != 200:
        raise RuntimeError(f"TwelveData HTTP {r.status_code}: {r.text[:200]}")

    j = r.json()
    if "status" in j and j.get("status") == "error":
        raise RuntimeError(f"TwelveData error: {j.get('message')}")
    values = j.get("values")
    if not values:
        raise RuntimeError(f"No 'values' in TwelveData response: {str(j)[:200]}")

    # values are dicts with keys: datetime, open, high, low, close, volume (strings)
    # Ensure ascending by time (we also asked order=ASC)
    opens, highs, lows, closes, times = [], [], [], [], []
    for row in values:
        times.append(row["datetime"])  # already UTC ISO like '2025-08-22 04:00:00'
        opens.append(float(row["open"]))
        highs.append(float(row["high"]))
        lows.append(float(row["low"]))
        closes.append(float(row["close"]))

    return opens, highs, lows, closes, times
