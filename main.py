# main.py — full runner (fetch → score → local agent → Telegram)
# Works with: core.py and agent_policy.py

from __future__ import annotations
import os, json, argparse, asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

# ---- project imports (your existing modules) ----
from core import (
    get_candles, build_bias, last_bar_time, atr, risk_plan,
    reconcile_action, label_confidence, provenance_line, crosscheck_msg,
    utc_iso, valid_until_iso, within_ttl, simple_levels, fmt_support_resistance,
    macro_note_placeholder, round_px, signal_id, detect_profile, PROFILE_NOTE
)
from agent_policy import AgentPolicy

load_dotenv()

# ---------------- Telegram ----------------
def tg_send_markdown(text: str) -> bool:
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("Telegram not configured (.env missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        return False
    try:
        url = f"https://api.telegram.org/bot{tok}/sendMessage"
        payload = {"chat_id": chat, "text": text, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"Telegram send failed: {r.status_code} {r.text}")
            return False
        return True
    except Exception as e:
        print(f"Telegram exception: {e}")
        return False

# ------------- Builders -------------------
def compute_confidence_1to5(score16: int, score6: float) -> int:
    # map (0..16 + 0..6) into 1..5 simply
    total = max(0.0, min(22.0, float(score16) + float(score6)))
    frac = total / 22.0
    # 1..5 bands
    if frac >= 0.80: return 5
    if frac >= 0.60: return 4
    if frac >= 0.40: return 3
    if frac >= 0.20: return 2
    return 1

def reasons_short(bias_info: Dict[str, Any]) -> List[str]:
    out = []
    r = bias_info.get("reasons", [])
    # map terse flags to readable snippets
    mapper = {
        "trend_up": "Trend ↑",
        "trend_down": "Trend ↓",
        "rsi_bull": "RSI bullish",
        "rsi_bear": "RSI bearish",
        "macd_gt_signal": "MACD > signal",
        "macd_lt_signal": "MACD < signal",
        "atr_ok": "ATR ok",
    }
    for k in r:
        if k in mapper:
            out.append(mapper[k])
    return out[:6]  # keep concise

def build_signal_json(symbol: str, tf_minutes: int) -> Dict[str, Any]:
    # fetch
    df, used_source, y_sym, td_sym, pretty_tf = get_candles(symbol, tf_minutes)
    if df is None or df.empty:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "symbol": symbol,
            "timeframe": pretty_tf,
            "utc_time": now,
            "action": "WAIT",
            "score16": 0,
            "score6": 0,
            "why_short": [],
            "risk_notes": ["No data"],
            "conflicts": [],
            "confidence_1to5": 1,
            "telegram_commentary": "No data from sources.",
            "meta": {"source": used_source, "y_sym": y_sym, "td_sym": td_sym, "tf_label": pretty_tf, "rows": 0}
        }

    # core analytics
    bias_info = build_bias(df)                             # contains: bias, score16, score6, reasons
    score16 = int(bias_info.get("score16", 0))
    score6  = float(bias_info.get("score6", 0.0))
    bias    = bias_info.get("bias", "mixed")

    last_px = float(df["Close"].iloc[-1])
    last_dt = last_bar_time(df)
    ttl_ok  = within_ttl(last_dt, max_age_min=120)

    # raw action by bias → reconcile with confidence
    score01 = max(0.0, min(1.0, score6 / 6.0))
    raw_action = "SELL" if bias == "bearish" else ("BUY" if bias == "bullish" else "WAIT")
    action_final = reconcile_action(raw_action, score01)
    if not ttl_ok:
        action_final = "WAIT"

    # S/R + ATR plan
    res, sup = simple_levels(df)
    s_res_line = fmt_support_resistance(res, sup, symbol)
    atr_val = atr(df)
    plan = risk_plan(action_final, symbol, last_px, atr_val)

    # meta/provenance
    prov = provenance_line(used_source, y_sym, pretty_tf, len(df))
    build_tag = f"ID:{signal_id({'sym':symbol,'tf':tf_minutes,'src':used_source,'last':round_px(symbol,last_px),'score16':score16,'score6':score6,'bias':bias,'ts':utc_iso()})}"
    net_prof = detect_profile().name

    why = reasons_short(bias_info)
    risks = []
    if not ttl_ok: risks.append("stale")
    if plan is None: risks.append("no ATR plan")

    conf_1to5 = compute_confidence_1to5(score16, score6)

    # commentary for the agent to expand
    base_comment = []
    if "Trend ↑" in why: base_comment.append("Uptrend")
    if "Trend ↓" in why: base_comment.append("Downtrend")
    if "MACD > signal" in why: base_comment.append("MACD bullish")
    if "MACD < signal" in why: base_comment.append("MACD bearish")
    if "RSI bullish" in why: base_comment.append("RSI > 50")
    if "RSI bearish" in why: base_comment.append("RSI < 50")
    commentary = ", ".join(base_comment) if base_comment else "Mixed signals"

    payload = {
        "symbol": symbol,
        "timeframe": pretty_tf,
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "action": action_final,
        "score16": score16,
        "score6": score6,
        "why_short": why,
        "risk_notes": risks if risks else ["normal"],
        "conflicts": [],
        "confidence_1to5": conf_1to5,
        "telegram_commentary": commentary,
        "levels": {
            "support": [float(x) for x in sup[:3]],
            "resistance":[float(x) for x in res[:3]]
        },
        "plan": plan or {},
        "meta": {
            "source": used_source,
            "y_sym": y_sym,
            "td_sym": td_sym,
            "tf_label": pretty_tf,
            "rows": len(df),
            "ttl_ok": ttl_ok,
            "profile": net_prof,
            "provenance": prov,
            "profile_note": PROFILE_NOTE
        }
    }
    return payload

def render_via_agent(payload: Dict[str,Any]) -> str:
    agent = AgentPolicy()
    try:
        s = json.dumps(payload)
        out = agent.process_signal(s)
        return out
    except Exception as e:
        # fallback minimal text if agent fails
        return (
            f"📊 {payload.get('symbol')} ({payload.get('timeframe')})\n"
            f"Time: {payload.get('utc_time')}\n"
            f"Action: {payload.get('action')}  Score: {payload.get('score16')}/16 + {payload.get('score6')}/6\n"
            f"Why: {', '.join(payload.get('why_short', [])) or 'n/a'}\n"
            f"Risk: {', '.join(payload.get('risk_notes', [])) or 'n/a'}\n"
            f"Note: agent error: {e}"
        )

# ------------- CLI ------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="TomaMobileForexBot runner")
    ap.add_argument("--symbol", required=False, default=os.getenv("DEFAULT_SYMBOL","EURUSD=X"),
                    help="Yahoo symbol or pair e.g. EURUSD=X, XAUUSD=X, EUR/USD")
    ap.add_argument("--tf", type=int, default=int(os.getenv("DEFAULT_TIMEFRAME","60")),
                    help="timeframe minutes (60=H1, 240=H4)")
    ap.add_argument("--no-telegram", action="store_true", help="print only, do not send to Telegram")
    return ap.parse_args()

async def main_async():
    args = parse_args()
    payload = build_signal_json(args.symbol, args.tf)
    msg = render_via_agent(payload)

    print("\n" + msg + "\n")
    if not args.no_telegram:
        tg_send_markdown(msg)

if __name__ == "__main__":
    asyncio.run(main_async())
