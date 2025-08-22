"""
helpers/core_td_patch.py
Replacement for TwelveData candles, normalized for core.py.
"""

import os, json, requests, pandas as pd, importlib
from datetime import timezone

# --- safe getenv + log_error fallbacks ---
def _safe_getenv(key, default=None):
    try:
        v = os.getenv(key)
        return v if v and str(v).strip() != "" else default
    except: return default

def _log_error(msg):
    try: print("ERROR:", msg)
    except: pass

try:
    from utils import safe_getenv  # type: ignore
except: safe_getenv = _safe_getenv
try:
    from utils import log_error  # type: ignore
except: log_error = _log_error

TD_BASE = "https://api.twelvedata.com/time_series"

# --- map minutes to TwelveData interval strings ---
def _interval_str(tf_minutes: int) -> str:
    mapping = {
        1:"1min", 5:"5min", 15:"15min", 30:"30min", 45:"45min",
        60:"1h", 120:"2h", 240:"4h", 480:"8h", 1440:"1day",
        10080:"1week", 43200:"1month"
    }
    return mapping.get(tf_minutes, f"{tf_minutes}min")

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"])
    df = df.rename(columns={
        "open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"
    })
    if "Volume" not in df: df["Volume"]=0.0
    for c in ["Open","High","Low","Close","Volume"]:
        if c in df: df[c]=pd.to_numeric(df[c], errors="coerce")
    if "datetime" in df:
        df.index=pd.to_datetime(df["datetime"],utc=True,errors="coerce")
        df=df.drop(columns=["datetime"])
    elif not isinstance(df.index,pd.DatetimeIndex):
        df.index=pd.to_datetime(df.index,utc=True,errors="coerce")
    if df.index.tz is None: df.index=df.index.tz_localize(timezone.utc)
    df=df.sort_index()
    df[["Open","High","Low","Close","Volume"]]=df[["Open","High","Low","Close","Volume"]].fillna(method="ffill").fillna(0.0)
    return df

def get_candles(symbol: str, tf_minutes: int):
    """Main entrypoint: returns (df, src, tf_lbl)."""
    apikey=safe_getenv("TWELVE_DATA_API_KEY",None)
    if not apikey:
        log_error("TWELVE_DATA_API_KEY missing")
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"]), "TD", f"{tf_minutes}m"
    params={"symbol":symbol,"interval":_interval_str(tf_minutes),
            "apikey":apikey,"outputsize":"500","format":"JSON"}
    try:
        r=requests.get(TD_BASE,params=params,timeout=15); r.raise_for_status()
        data=r.json(); values=data.get("values",[])
        if not values:
            log_error(f"TwelveData empty for {symbol} {tf_minutes}m: {json.dumps(data)[:200]}")
            return pd.DataFrame(columns=["Open","High","Low","Close","Volume"]), "TD", f"{tf_minutes}m"
        df=pd.DataFrame(values); df=_normalize_df(df)
        return df,"TD",_interval_str(tf_minutes)
    except Exception as e:
        log_error(f"TwelveData fetch failed {symbol} {tf_minutes}m: {e}")
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"]), "TD", f"{tf_minutes}m"

# --- monkey patch into core automatically ---
try:
    core=importlib.import_module("core")
    core.get_candles=get_candles
except Exception as e:
    log_error(f"core_td_patch note: {e}")
