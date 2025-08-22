#!/usr/bin/env python3
"""
agent_policy.py
- Reads a JSON payload (stdin or file) with your bot's analysis
- Applies veto rules for 16+6 system
- Outputs:
  1) Final structured JSON (to stdout)
  2) A clean Telegram message (to stdout after a divider)
No external AI calls. Safe to run offline.
"""

from __future__ import annotations
import sys, json, math
from datetime import datetime, timezone

DIVIDER = "\n" + ("-"*48) + "\n"

REQUIRED_TOP = ["symbol","timeframe","utc_build","price","score16","score6","tech","fund","pre_action"]

def _now_utc_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def band_from_score01(s01: float) -> str:
    if s01 >= 0.70: return "HIGH"
    if s01 >= 0.50: return "MEDIUM"
    if s01 >= 0.30: return "LOW"
    return "WEAK"

def veto_checks(payload: dict) -> list[str]:
    """Return list of veto reasons. Any veto → final action = WAIT."""
    v = []
    fund = payload.get("fund", {})
    # 6-point fundamentals (explicit vetoes)
    if fund.get("no_red_news_1h") is False: v.append("red news < 1h")
    if fund.get("spread_ok") is False:      v.append("spread too high")
    if fund.get("not_mid_candle") is False: v.append("mid-candle window")
    # TTL freshness veto
    ttl_ok = payload.get("ttl_ok", True)
    if ttl_ok is False: v.append("stale data")
    # Optional: source mismatch/cross-check
    if payload.get("price_crosscheck") == "mismatch":
        v.append("cross-source price mismatch")
    return v

def pick_direction(tech: dict) -> str:
    """Directional hint from tech flags. Keep simple + explainable."""
    bull = int(tech.get("ema9_gt_21",0)) + int(tech.get("macd_bull",0)) + int(tech.get("rsi_gt_60",0))
    bear = int(tech.get("ema9_lt_21",0)) + int(tech.get("macd_bear",0)) + int(tech.get("rsi_lt_40",0))
    if bull > bear: return "BUY"
    if bear > bull: return "SELL"
    return "WAIT"

def explain_why(tech: dict, fund: dict) -> list[str]:
    out = []
    if tech.get("ema9_gt_21"): out.append("EMA9>21")
    if tech.get("ema9_lt_21"): out.append("EMA9<21")
    if tech.get("ema20_gt_50"): out.append("EMA20>50")
    if tech.get("ema20_lt_50"): out.append("EMA20<50")
    if tech.get("rsi_gt_60"): out.append("RSI>60")
    if tech.get("rsi_lt_40"): out.append("RSI<40")
    if tech.get("rsi_div"): out.append("RSI divergence")
    if tech.get("macd_bull"): out.append("MACD>signal")
    if tech.get("macd_bear"): out.append("MACD<signal")
    if tech.get("adx_gt_20"): out.append("ADX>20")
    if tech.get("atr_zone"): out.append("ATR ok")
    if tech.get("pattern"): out.append(f"pattern:{tech.get('pattern_type','?')}")
    if tech.get("mtf_confluence"): out.append("MTF confluence")
    if tech.get("fibo_touch"): out.append("Fib area")
    if tech.get("sr_break"): out.append("S/R break")
    if tech.get("high_volume"): out.append("Volume↑")
    if tech.get("momentum_body"): out.append("Momentum candle")
    if tech.get("above_200"): out.append("Above 200 EMA")
    # fund hints (non-veto positives)
    if fund.get("news_sentiment_ok"): out.append("News sentiment ok")
    if fund.get("no_cb_conflict"): out.append("No CB conflict")
    if fund.get("tg_agreement"): out.append("External signal agreement")
    return out

def build_message(p: dict, final_action: str, conf_band: str, score16: int, score6: int, reasons: list[str], risk_notes: list[str]) -> str:
    sym = p["symbol"]; tf = p["timeframe"]
    price = p.get("price","?")
    ts = p.get("utc_build", _now_utc_iso())
    s_line = f"📊 *{sym}* ({tf})"
    t_line = f"🕒 Signal Time (UTC): `{ts}`"
    a_line = f"📈 Action: *{final_action}*   |   Confidence: *{conf_band}*"
    sc_line = f"📊 Score: {score16}/16 + {score6}/6"
    r_line = f"🧠 Reason: " + (", ".join(reasons) if reasons else "mixed")
    risk_line = "⚠️ Risk: " + (", ".join(risk_notes) if risk_notes else "normal")
    spread = p.get("spread_pips")
    sp_line = f"📉 Spread: {spread:.1f} pips" if isinstance(spread,(int,float)) else None
    # levels (optional)
    sup = p.get("support",[]) or []
    res = p.get("resistance",[]) or []
    lvl = []
    if sup: lvl.append("Support: " + ", ".join(map(str, sup[:3])))
    if res: lvl.append("Resistance: " + ", ".join(map(str, res[:3])))
    lvl_block = "\n".join(lvl) if lvl else None
    # provenance
    prov = p.get("provenance","")
    lines = [s_line, t_line, a_line, sc_line, r_line, risk_line]
    if sp_line: lines.append(sp_line)
    if lvl_block: lines.append(lvl_block)
    if prov: lines.append(prov)
    return "\n".join(lines)

def main():
    # read JSON from file path or stdin
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        raw = open(sys.argv[1],"r",encoding="utf-8").read()
    else:
        raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error":"invalid_json","detail":str(e)}))
        return

    # basic schema check
    missing = [k for k in REQUIRED_TOP if k not in payload]
    if missing:
        print(json.dumps({"error":"missing_fields","fields":missing}))
        return

    # scores
    score16 = int(payload.get("score16",0))
    score6  = int(payload.get("score6",0))
    score01 = (score16/16.0)*0.7 + (score6/6.0)*0.3
    score01 = clamp01(score01)
    conf_band = band_from_score01(score01)

    tech = payload.get("tech",{})
    fund = payload.get("fund",{})

    # vetoes
    vetoes = veto_checks(payload)
    raw_dir = payload.get("pre_action") or pick_direction(tech)
    final_action = "WAIT" if vetoes else raw_dir
    # downgrade very weak signals
    if score01 < 0.30:
        final_action = "WAIT"

    reasons = explain_why(tech,fund)
    risk_notes = []
    if "red news < 1h" in vetoes: risk_notes.append("calendar risk")
    if "spread too high" in vetoes: risk_notes.append("spread")
    if "mid-candle window" in vetoes: risk_notes.append("mid-candle")
    if "stale data" in vetoes: risk_notes.append("stale")
    if "cross-source price mismatch" in vetoes: risk_notes.append("price mismatch")

    # final JSON
    out = {
        "symbol": payload["symbol"],
        "timeframe": payload["timeframe"],
        "utc_build": payload.get("utc_build"),
        "price": payload.get("price"),
        "final_action": final_action,
        "confidence_band": conf_band,
        "score16": score16,
        "score6": score6,
        "score01": round(score01,3),
        "reasons": reasons,
        "vetoes": vetoes,
        "risk_notes": risk_notes,
        "valid_until": payload.get("valid_until"),
    }
    print(json.dumps(out, ensure_ascii=False))

    # pretty Telegram message
    print(DIVIDER)
    print(build_message(payload, final_action, conf_band, score16, score6, reasons, risk_notes))

if __name__ == "__main__":
    main()
