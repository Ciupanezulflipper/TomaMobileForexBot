#!/usr/bin/env python3
"""
analysis_engine.py — ONE-FILE research+analysis module for the mobile bot.

Inputs:
  - Pairs like "EURUSD", "GBPUSD", "XAUUSD" (no slash)
  - Uses env keys if available: ALPHA_VANTAGE_API_KEY, FINNHUB_API_KEY, NEWS_API_KEY

Outputs:
  - dict with sections per your spec + render_text() helper for Telegram
"""

import os, time, math, json, textwrap, datetime as dt
from typing import List, Dict, Any, Tuple, Optional
import requests
import pandas as pd

ALPHA = os.getenv("ALPHA_VANTAGE_API_KEY", "")
FINNHUB = os.getenv("FINNHUB_API_KEY", "")
NEWSAPI = os.getenv("NEWS_API_KEY", "")

UTC = dt.timezone.utc

def _since(hours=24):
    return (dt.datetime.now(UTC) - dt.timedelta(hours=hours)).isoformat()

def _safe_get(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def _fx_intraday_alpha(pair: str, interval="60min", limit=300) -> Optional[pd.DataFrame]:
    if not ALPHA: return None
    base, quote = pair[:3], pair[3:]
    url = "https://www.alphavantage.co/query"
    params = dict(function="FX_INTRADAY", from_symbol=base, to_symbol=quote,
                  interval=interval, apikey=ALPHA, outputsize="full")
    js = _safe_get(url, params)
    key = f"Time Series FX ({interval})"
    if not js or key not in js: return None
    df = pd.DataFrame(js[key]).T.rename(columns={
        "1. open":"open","2. high":"high","3. low":"low","4. close":"close"
    }).astype(float).tail(limit)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df

def _econ_calendar_finnhub() -> List[Dict[str,Any]]:
    if not FINNHUB: return []
    url = "https://finnhub.io/api/v1/calendar/economic"
    end = dt.datetime.now(UTC).date().isoformat()
    start = (dt.datetime.now(UTC) - dt.timedelta(days=2)).date().isoformat()
    js = _safe_get(url, {"from":start, "to":end, "token":FINNHUB})
    out = []
    for row in (js.get("economicCalendar", []) if js else []):
        # Normalize
        when = row.get("time", "") or row.get("datetime", "") or ""
        cc = row.get("country", "")
        event = row.get("event", row.get("indicator", ""))
        actual = row.get("actual")
        forecast = row.get("estimate", row.get("forecast"))
        out.append({
            "time": when,
            "country": cc,
            "event": event,
            "actual": actual,
            "forecast": forecast
        })
    return out

def _news_newsapi(pair:str) -> List[Dict[str,Any]]:
    if not NEWSAPI: return []
    q = f'"{pair}" OR forex OR "FX"'
    url = "https://newsapi.org/v2/everything"
    js = _safe_get(url, {
        "q": q,
        "from": (dt.datetime.now(UTC)-dt.timedelta(hours=24)).isoformat(),
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "apiKey": NEWSAPI
    })
    out=[]
    for art in (js.get("articles",[]) if js else []):
        out.append({
            "time": art.get("publishedAt"),
            "source": art.get("source",{}).get("name","News"),
            "title": art.get("title",""),
            "url": art.get("url","")
        })
    return out

def _ta(df: pd.DataFrame) -> Dict[str,Any]:
    if df is None or df.empty:
        return {"bias":"Neutral","notes":["No price data."],"levels":{}}

    close = df["close"]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    rsi = _rsi(close, 14)

    last = close.iloc[-1]
    lvls = {
        "last": round(last,5),
        "ema9": round(ema9.iloc[-1],5),
        "ema21": round(ema21.iloc[-1],5)
    }

    score = 0
    notes=[]
    if ema9.iloc[-2] < ema21.iloc[-2] and ema9.iloc[-1] > ema21.iloc[-1]:
        score += 2; notes.append("EMA9>EMA21 bull cross")
    if ema9.iloc[-2] > ema21.iloc[-2] and ema9.iloc[-1] < ema21.iloc[-1]:
        score -= 2; notes.append("EMA9<EMA21 bear cross")

    if macd.iloc[-1] > macd_sig.iloc[-1]: score += 1
    else: score -= 1

    if rsi.iloc[-1] > 60: score += 1
    elif rsi.iloc[-1] < 40: score -= 1

    bias = "Bullish" if score>=2 else "Bearish" if score<=-2 else "Neutral"
    return {"bias":bias, "score":score, "rsi": round(float(rsi.iloc[-1]),1),
            "macd": round(float(macd.iloc[-1]-macd_sig.iloc[-1]),5),
            "levels": lvls, "notes":notes}

def _rsi(series: pd.Series, period=14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1*delta.clip(upper=0)
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up/ma_down.replace(0, 1e-9)
    return 100 - (100/(1+rs))

def _impact_tag(event: str) -> str:
    key = event.lower()
    if any(k in key for k in ["cpi","payroll","interest rate","rate decision","jobs","gdp"]):
        return "High"
    if any(k in key for k in ["pmi","confidence","trade balance","minutes","speech"]):
        return "Medium"
    return "Low"

def _sentiment_from_event(event:str, country:str, pair:str) -> str:
    base, quote = pair[:3].upper(), pair[3:].upper()
    # crude heuristic: positive US data -> USD bullish (pair with USD as quote goes down)
    key = event.lower()
    if country.upper() in [base, quote]:
        if any(k in key for k in ["hot","beats","surprise","hawk","tighten","raise","strong"]):
            # stronger country currency -> if it's base -> pair up, if quote -> pair down
            return "Bullish" if country.upper()==base else "Bearish"
        if any(k in key for k in ["miss","weak","dovish","cut","cool"]):
            return "Bearish" if country.upper()==base else "Bullish"
    return "Neutral"

def analyze_pair(pair: str="EURUSD") -> Dict[str,Any]:
    pair = pair.upper().replace("/","")
    # 1) Prices & TA
    df = _fx_intraday_alpha(pair)  # 60m
    ta = _ta(df)

    # 2) Econ calendar (last 48h window from Finnhub)
    econ = _econ_calendar_finnhub()

    # 3) News (24h)
    news = _news_newsapi(pair)

    # Build matrix (top 8 mixed from econ+news)
    events=[]
    now = dt.datetime.now(UTC)
    for e in econ[:10]:
        ts = e.get("time") or ""
        event = e.get("event","")
        sent = _sentiment_from_event(event, e.get("country",""), pair)
        events.append({
            "time": ts or "",
            "source": e.get("country","Econ"),
            "headline": event,
            "impact": _impact_tag(event),
            "sentiment": sent,
            "price_effect": "n/a",
            "confidence": "6/10"
        })
    for n in news[:10]:
        events.append({
            "time": n.get("time",""),
            "source": n.get("source","News"),
            "headline": n.get("title",""),
            "impact": "Medium",
            "sentiment": "Neutral",
            "price_effect": "n/a",
            "confidence": "6/10"
        })

    # Sentiment aggregation
    bull = sum(1 for e in events if e["sentiment"]=="Bullish")
    bear = sum(1 for e in events if e["sentiment"]=="Bearish")
    neu  = sum(1 for e in events if e["sentiment"]=="Neutral")
    total = max(1, bull+bear+neu)
    inst_cons = "Bullish" if bull>bear else "Bearish" if bear>bull else "Neutral"

    # Support/Resistance quick peek from last 100 bars
    sr = {}
    if df is not None and len(df)>=50:
        sub = df.tail(100)
        sr = {
            "support": round(sub["low"].rolling(10).min().iloc[-1],5),
            "resistance": round(sub["high"].rolling(10).max().iloc[-1],5)
        }

    # Signal (very simple: TA score)
    if ta["bias"]=="Bullish": signal="BUY"
    elif ta["bias"]=="Bearish": signal="SELL"
    else: signal="HOLD"

    exec_summary = (
        f"{pair}: TA bias **{ta['bias']}** (score {ta['score']}). "
        f"RSI {ta.get('rsi','?')}, MACDΔ {ta.get('macd','?')}. "
        f"Last {ta['levels'].get('last','?')} | EMA9 {ta['levels'].get('ema9','?')} | "
        f"EMA21 {ta['levels'].get('ema21','?')}. "
        f"News {len(news)} / Econ {len(econ)} items in 24h. "
        f"Provisional signal: **{signal}** (low-latency model)."
    )

    out = {
        "pair": pair,
        "executive_summary": exec_summary,
        "events": events[:12],
        "sentiment": {
            "institutional_consensus": inst_cons,
            "technical_bias": ta["bias"],
            "flow_data": "Neutral",
            "overall": ta["bias"],
            "conviction": "Medium" if abs(ta["score"])>=2 else "Low"
        },
        "technical": {
            "levels": ta["levels"],
            "support_resistance": sr,
            "notes": ta["notes"]
        },
        "implications": {
            "support": sr.get("support"),
            "resistance": sr.get("resistance"),
            "expected_range": "~0.3% - 0.7% (intraday)",
            "risk_mgmt": "Use hard SL beyond opposite S/R; size ≤1% acct risk."
        },
        "confidence": {
            "overall": 7 if (news or econ) and df is not None else 5,
            "conviction_level": "Medium",
            "data_quality": "Mixed (API-based)",
            "market_conditions": "Normal" if df is not None else "Uncertain"
        },
        "signal": signal
    }
    return out

def render_text(analysis: Dict[str,Any]) -> str:
    pair = analysis["pair"]
    s = ["📊 *24h Analysis — " + pair + "*",
         "",
         "— *Executive Summary* —",
         analysis["executive_summary"],
         "",
         "— *Key Events (last 24h)* —"]
    if analysis["events"]:
        s.append("Time | Src | Impact | Sent | Headline")
        for e in analysis["events"]:
            t = (e.get("time") or "")[:16].replace("T"," ")
            s.append(f"`{t}` | {e['source']} | {e['impact']} | {e['sentiment']} | {e['headline'][:60]}")
    else:
        s.append("_No recent events available._")

    tech = analysis["technical"]
    imp = analysis["implications"]
    s += [
        "",
        "— *Sentiment* —",
        f"Institutional: *{analysis['sentiment']['institutional_consensus']}* | "
        f"Technical: *{analysis['sentiment']['technical_bias']}* | "
        f"Overall: *{analysis['sentiment']['overall']}* ({analysis['sentiment']['conviction']})",
        "",
        "— *Technical Levels* —",
        f"Last: `{tech['levels'].get('last')}`  | EMA9: `{tech['levels'].get('ema9')}`  | EMA21: `{tech['levels'].get('ema21')}`",
        f"Support: `{imp.get('support')}` | Resistance: `{imp.get('resistance')}`",
        "",
        "— *Trading Implications* —",
        f"Signal: *{analysis['signal']}*  | Range: {imp['expected_range']}",
        f"Risk: {imp['risk_mgmt']}",
        "",
        "— *Confidence* —",
        f"Overall: {analysis['confidence']['overall']}/10  | "
        f"Data: {analysis['confidence']['data_quality']}  | "
        f"Market: {analysis['confidence']['market_conditions']}",
    ]
    txt = "\n".join(s)
    # Telegram safe cap
    return txt[:3800]
