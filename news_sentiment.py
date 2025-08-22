#!/usr/bin/env python3
# news_sentiment.py  — standalone (adds sentiment), no edits to existing code
import os, sys, json, argparse, datetime, re
from typing import List, Dict, Any
try:
    import requests
except Exception as e:
    print(json.dumps({"error":"requests_not_available","detail":str(e)})); sys.exit(1)

def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00","Z")

def _symbol_to_query(symbol: str) -> str:
    s = symbol.upper().strip().replace(" ", "")
    if re.fullmatch(r"[A-Z]{1,6}", s):
        aliases = {"TSLA":"Tesla","AAPL":"Apple","MSFT":"Microsoft","GOOGL":"Google OR Alphabet",
                   "AMZN":"Amazon","META":"Meta OR Facebook","NVDA":"Nvidia"}
        extra = aliases.get(s, "")
        return f'({s}{(" OR " + extra) if extra else ""})'
    if s in ("XAUUSD","XAU/USD","XAUUSDT","GOLD","GOLDUSD"):
        return '(XAUUSD OR "gold price" OR gold)'
    s = s.replace("/","")
    if re.fullmatch(r"[A-Z]{6,7}", s):
        base, quote = s[:3], s[3:6]
        return f'("{base}{quote}" OR "{base} {quote}" OR {base}) AND ({quote})'
    return symbol

def _load_vader():
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except Exception:
        return None

_POS = set("good,gain,beats,beat,up,soar,bull,bullish,positive,optimistic,upgrade,raised,breakout,strong".split(","))
_NEG = set("bad,loss,miss,down,drop,fall,bear,bearish,negative,pessimistic,downgrade,cut,weak,warning,probe".split(","))

def _simple_score(txt: str) -> float:
    words = re.findall(r"[a-zA-Z]+", txt.lower())
    pos = sum(1 for w in words if w in _POS)
    neg = sum(1 for w in words if w in _NEG)
    total = pos + neg
    return 0.0 if total == 0 else (pos - neg) / total

def _label_from_compound(c: float) -> str:
    if c >= 0.05: return "positive"
    if c <= -0.05: return "negative"
    return "neutral"

def _get_news_newsapi(query: str, api_key: str, limit: int = 20):
    url = "https://newsapi.org/v2/everything"
    params = {"q": query, "language": "en", "sortBy": "publishedAt",
              "pageSize": max(5, min(limit, 100)), "apiKey": api_key}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("articles", [])

def _score_headlines(headlines: List[str]) -> Dict[str, float|str]:
    vader = _load_vader()
    scores = []
    for h in headlines:
        if not h: continue
        if vader:
            s = vader.polarity_scores(h).get("compound", 0.0)
        else:
            s = _simple_score(h)
        scores.append(float(s))
    avg = float(sum(scores)/len(scores)) if scores else 0.0
    return {"avg_compound": avg, "label": _label_from_compound(avg)}

def run(symbol: str, limit: int = 20) -> Dict[str, Any]:
    query = _symbol_to_query(symbol)
    headlines, provider, note = [], None, None
    news_key = os.getenv("NEWS_API_KEY")
    if news_key:
        try:
            arts = _get_news_newsapi(query, news_key, limit)
            provider = "newsapi"
            headlines = [a.get("title","") for a in arts if a.get("title")]
        except Exception as e:
            note = f"newsapi_error: {type(e).__name__}: {e}"
    sc = _score_headlines(headlines[:12])
    news = {"provider": provider or "none", "query": query, "count": len(headlines),
            "avg_compound": round(sc["avg_compound"],4), "label": sc["label"],
            "headlines": headlines[:3], "built_utc": _utc_now_iso(), "note": note}
    ff = {"news_sentiment_ok": (sc["label"] != "negative")}
    return {"news": news, "fundamental_flags": ff}

def main():
    ap = argparse.ArgumentParser(description="Fetch & score news sentiment (adds JSON, no edits elsewhere).")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = run(args.symbol, args.limit)
    print(json.dumps(res, ensure_ascii=False) if args.json else
          f'📰 {args.symbol}: {res["news"]["label"]} (avg={res["news"]["avg_compound"]}) • {res["news"]["provider"]}\n'
          + "\n".join(" • "+h for h in res["news"]["headlines"]))

if __name__ == "__main__":
    main()
