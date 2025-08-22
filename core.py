# TomaMobileForexBot - core.py (strict-veto + expanded rules)
# FULL FILE, paste-as-one with EOF

from __future__ import annotations
import os, json, math, datetime as _dt
from typing import Tuple, Dict, List
import numpy as np
import pandas as pd

# ======================
# Utilities / logging
# ======================
def utc_iso() -> str:
    # timezone-aware UTC; Telegram examples look good with trailing Z
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00","Z")

def safe_getenv(k: str, default: str|None=None) -> str|None:
    return os.environ.get(k, default)

def log_error(msg: str, extra: Dict|None=None):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/error.log","a") as f:
            f.write(json.dumps({"ts": utc_iso(),"level":"ERROR","msg":msg, **(extra or {})})+"\n")
    except Exception:
        pass

# ======================
# Data fetch
# ======================
def _td_get(symbol: str, tf_minutes: int) -> Tuple[pd.DataFrame, str, str]:
    """Prefer TwelveData helper if present (helpers/core_td_patch.py)."""
    try:
        from helpers.core_td_patch import get_candles as td_get_candles
        return td_get_candles(symbol, tf_minutes)
    except Exception as e:
        log_error("TD helper missing/failing; using yfinance fallback", {"err": str(e)})
        return _yf_get(symbol, tf_minutes)

def _yf_symbol(sym: str) -> str:
    # light mapping for fallback
    m = {
        "EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","AUD/USD":"AUDUSD=X","NZD/USD":"NZDUSD=X",
        "USD/JPY":"JPY=X","USD/CHF":"CHF=X","USD/CAD":"CAD=X",
        "XAU/USD":"XAUUSD=X","XAG/USD":"XAGUSD=X"
    }
    return m.get(sym, sym)

def _yf_get(symbol: str, tf_minutes: int) -> Tuple[pd.DataFrame, str, str]:
    try:
        import yfinance as yf
        yf_sym = _yf_symbol(symbol)
        period = "7d" if tf_minutes <= 60 else "60d"
        interval = f"{tf_minutes}m"
        data = yf.download(yf_sym, period=period, interval=interval, progress=False, auto_adjust=False)
        if data is None or data.empty:
            raise RuntimeError("yfinance returned empty")
        df = pd.DataFrame(data)[["Open","High","Low","Close","Volume"]].dropna()
        df.index = pd.to_datetime(df.index)
        # Invert if symbol is quoted as XXX=X (JPY, CHF, CAD) to get USD/XXX pricing
        if symbol in ("USD/JPY","USD/CHF","USD/CAD"):
            for c in ["Open","High","Low","Close"]:
                df[c] = 1.0/df[c]
        return df, "YF", f"{tf_minutes}m"
    except Exception as e:
        log_error("yfinance fallback failed", {"symbol": symbol, "tf": tf_minutes, "err": str(e)})
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"]), "NONE", f"{tf_minutes}m"

def get_candles(symbol: str, tf_minutes: int) -> Tuple[pd.DataFrame, str, str]:
    return _td_get(symbol, tf_minutes)

# ======================
# Indicators
# ======================
def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=max(2, n//2)).mean()

def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    d = close.diff()
    up = np.where(d>0, d, 0.0)
    dn = np.where(d<0, -d, 0.0)
    up = pd.Series(up, index=close.index).ewm(alpha=1/length, adjust=False).mean()
    dn = pd.Series(dn, index=close.index).ewm(alpha=1/length, adjust=False).mean()
    rs = up/(dn+1e-12)
    return 100 - (100/(1+rs))

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h,l,c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([(h-l).abs(), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def _macd(close: pd.Series, fast=12, slow=26, sig=9):
    macd = _ema(close, fast) - _ema(close, slow)
    signal = _ema(macd, sig)
    hist = macd - signal
    return macd, signal, hist

def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    # simplified Wilder ADX
    h,l,c = df["High"], df["Low"], df["Close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm  = np.where((up>dn) & (up>0), up, 0.0)
    minus_dm = np.where((dn>up) & (dn>0), dn, 0.0)
    tr = pd.concat([(h-l).abs(), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di  = 100 * pd.Series(plus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / (atr+1e-12)
    minus_di = 100 * pd.Series(minus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / (atr+1e-12)
    dx = ( (plus_di - minus_di).abs() / ((plus_di + minus_di)+1e-12) ) * 100
    return dx.ewm(alpha=1/n, adjust=False).mean()

def _engulf(prev_o, prev_c, o, c):
    bull = (c>o) and (prev_c<prev_o) and (o<=prev_c) and (c>=prev_o)
    bear = (c<o) and (prev_c>prev_o) and (o>=prev_c) and (c<=prev_o)
    return bull, bear

def _big_body(o,h,l,c,pct=0.6):
    rng = max(h-l, 1e-12); body = abs(c-o)
    up = (body/rng)>=pct and (c>o)
    dn = (body/rng)>=pct and (c<o)
    return up, dn

def _pivots(series: pd.Series, left=3, right=3):
    # simple swing detection for divergence/SR
    vals = series.values
    piv_hi, piv_lo = [], []
    for i in range(left, len(vals)-right):
        window = vals[i-left:i+right+1]
        if vals[i] == window.max():
            piv_hi.append((series.index[i], vals[i]))
        if vals[i] == window.min():
            piv_lo.append((series.index[i], vals[i]))
    return piv_hi, piv_lo

def _divergence(price: pd.Series, osc: pd.Series) -> Tuple[bool,bool]:
    """Return (bull_div, bear_div). Bullish: price lower low, osc higher low.
    Bearish: price higher high, osc lower high."""
    hi, lo = _pivots(price)
    hi_o, lo_o = _pivots(osc)
    if len(lo)>=2 and len(lo_o)>=2:
        p2,p1 = lo[-1][1], lo[-2][1]
        o2,o1 = lo_o[-1][1], lo_o[-2][1]
        bull = (p2 < p1) and (o2 > o1)
    else:
        bull = False
    if len(hi)>=2 and len(hi_o)>=2:
        p2,p1 = hi[-1][1], hi[-2][1]
        o2,o1 = hi_o[-1][1], hi_o[-2][1]
        bear = (p2 > p1) and (o2 < o1)
    else:
        bear = False
    return bull, bear

def _sr_break(price: pd.Series, left=3, right=3) -> Tuple[bool,bool]:
    """Detect recent support/resistance break (last bar)."""
    hi, lo = _pivots(price, left, right)
    last = price.iloc[-1]
    brk_up = any(last > ph for _,ph in hi[-2:]) if hi else False
    brk_dn = any(last < pl for _,pl in lo[-2:]) if lo else False
    return brk_up, brk_dn

# ======================
# Analyzer (16 tech + 6 fund stubs)
# ======================
def analyze_once(symbol: str, tf_minutes: int) -> Dict:
    df, src, tf_lbl = get_candles(symbol, tf_minutes)
    if df is None or df.empty:
        return {
            "symbol": symbol, "tf_lbl": tf_lbl, "src": src, "price": float("nan"),
            "score16": 0, "flags16": {}, "score6": 0, "flags6": {},
            "action": "WAIT", "why": ["No candles"], "built_utc": utc_iso(),
        }
    assert isinstance(df.index, pd.DatetimeIndex), "Index not DateTime"
    for c in ["Open","High","Low","Close","Volume"]:
        if c not in df.columns: raise AssertionError("Missing OHLCV")

    # last & prev
    if len(df)<2:
        last = df.iloc[-1]; prev = last
    else:
        last = df.iloc[-1]; prev = df.iloc[-2]

    close = df["Close"]; high = df["High"]; low = df["Low"]; vol = df["Volume"]

    # indicators
    ema9, ema21 = _ema(close,9), _ema(close,21)
    ema20, ema50 = _ema(close,20), _ema(close,50)
    ema200 = _ema(close,200)
    rsi14 = _rsi(close,14)
    atr14 = _atr(df,14)
    macd, macsig, mach = _macd(close)
    adx14 = _adx(df,14)
    vma20 = _sma(vol,20)

    # candlesticks
    bull_eng, bear_eng = _engulf(prev["Open"], prev["Close"], last["Open"], last["Close"])
    big_up, big_dn = _big_body(last["Open"], last["High"], last["Low"], last["Close"], pct=0.6)

    # RSI divergence
    rsi_bull_div, rsi_bear_div = _divergence(close, rsi14)

    # S/R break
    sr_up, sr_dn = _sr_break(close)

    # MACD crosses/flips (use last two bars)
    mac_cross_up  = macd.iloc[-2] <= macsig.iloc[-2] and macd.iloc[-1] > macsig.iloc[-1]
    mac_cross_dn  = macd.iloc[-2] >= macsig.iloc[-2] and macd.iloc[-1] < macsig.iloc[-1]
    hist_flip_up  = mach.iloc[-2] <= 0 and mach.iloc[-1] > 0
    hist_flip_dn  = mach.iloc[-2] >= 0 and mach.iloc[-1] < 0

    # Volume confirmation
    high_vol = bool(vol.iloc[-1] > (vma20.iloc[-1] * 1.1))  # 10% above vol MA

    # HTF confluence via resample
    htf_bull = False; htf_bear = False
    try:
        rule = {5:"60min", 60:"240min", 240:"1D"}.get(tf_minutes)
        if rule:
            df_h = df.resample(rule, label="right", closed="right").agg(
                {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            if len(df_h) >= 55:
                e20_h, e50_h = _ema(df_h["Close"],20), _ema(df_h["Close"],50)
                last_h = df_h["Close"].iloc[-1]
                htf_bull = bool(last_h > e20_h.iloc[-1] > e50_h.iloc[-1])
                htf_bear = bool(last_h < e20_h.iloc[-1] < e50_h.iloc[-1])
    except Exception as e:
        log_error("HTF confluence error", {"err": str(e)})

    # ----------------------
    # Define the 16 counted tech checks (exactly 16 keys)
    # ----------------------
    flags16: Dict[str,bool] = {
        "EMA9>EMA21":          bool(ema9.iloc[-1] > ema21.iloc[-1]),
        "EMA20>EMA50":         bool(ema20.iloc[-1] > ema50.iloc[-1]),
        "RSI>60":              bool(rsi14.iloc[-1] > 60),
        "RSI<40":              bool(rsi14.iloc[-1] < 40),
        "RSI bullish divergence": bool(rsi_bull_div),
        "RSI bearish divergence": bool(rsi_bear_div),
        "MACD cross ↑":        bool(mac_cross_up),
        "MACD cross ↓":        bool(mac_cross_dn),
        "ADX>20":              bool(adx14.iloc[-1] > 20),
        "ATR ok":              bool(atr14.iloc[-1] > 0),
        "Bullish engulfing":   bool(bull_eng),
        "Bearish engulfing":   bool(bear_eng),
        "High volume vs MA":   bool(high_vol),
        "Above 200 EMA":       bool(last["Close"] > ema200.iloc[-1]),
        "HTF confluence ↑":    bool(htf_bull),
        "S/R break (any)":     bool(sr_up or sr_dn),
    }
    score16 = sum(1 for v in flags16.values() if v)

    # Extra informative (not counted in /16 but shown in Why if true)
    extra_flags: Dict[str,bool] = {
        "Momentum big body ↑": bool(big_up),
        "Momentum big body ↓": bool(big_dn),
        "HTF confluence ↓":    bool(htf_bear),
        "MACD hist flip ↑":    bool(hist_flip_up),
        "MACD hist flip ↓":    bool(hist_flip_dn),
        "S/R break ↑":         bool(sr_up),
        "S/R break ↓":         bool(sr_dn),
        # room for: Fibonacci bounce/break, S/R retest, etc.
    }

    # ----------------------
    # Fundamentals/Sentiment stubs (0/6 until APIs wired)
    # ----------------------
    flags6: Dict[str,bool] = {
        "No red news next 1h": False,
        "News sentiment supports signal": False,
        "No CB conflict": False,
        "Spread acceptable": False,
        "External signal agreement": False,
        "Not mid-candle": False,
    }
    score6 = sum(1 for v in flags6.values() if v)

    # ----------------------
    # Decision: strict veto
    # ----------------------
    bull_keys = [
        "EMA9>EMA21","EMA20>EMA50","RSI>60","RSI bullish divergence","MACD cross ↑",
        "ADX>20","Bullish engulfing","High volume vs MA","Above 200 EMA","HTF confluence ↑",
        "S/R break (any)"  # direction-agnostic; refined by extra_flags if needed
    ]
    bear_keys = [
        "RSI<40","RSI bearish divergence","MACD cross ↓","Bearish engulfing",
        # use extra bear info as veto too:
    ]
    # Add extra bears to veto set
    bear_votes = sum(1 for k in bear_keys if flags16.get(k, False))
    if extra_flags["Momentum big body ↓"]: bear_votes += 1
    if extra_flags["HTF confluence ↓"]:    bear_votes += 1
    if extra_flags["MACD hist flip ↓"]:    bear_votes += 1
    if extra_flags["S/R break ↓"]:         bear_votes += 1

    bull_votes = sum(1 for k in bull_keys if flags16.get(k, False))
    if extra_flags["Momentum big body ↑"]: bull_votes += 1
    if extra_flags["MACD hist flip ↑"]:    bull_votes += 1
    if extra_flags["S/R break ↑"]:         bull_votes += 1

    if bull_votes > 0 and bear_votes > 0:
        action = "WAIT"
    elif bull_votes >= 3 and bear_votes == 0:
        action = "BUY"
    elif bear_votes >= 3 and bull_votes == 0:
        action = "SELL"
    else:
        action = "WAIT"

    # Why list: all true items (counted + extra)
    why = [k for k,v in flags16.items() if v] + [k for k,v in extra_flags.items() if v]

    return {
        "symbol": symbol,
        "tf_lbl": f"{tf_minutes}m",
        "src": src,
        "price": float(last["Close"]),
        "score16": score16,
        "flags16": flags16,
        "score6": score6,
        "flags6": flags6,
        "action": action,
        "why": why,
        "built_utc": utc_iso(),
    }
