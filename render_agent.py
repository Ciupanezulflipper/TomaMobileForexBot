#!/usr/bin/env python3
import json, sys, argparse, datetime
from pathlib import Path

# Optional Telegram; safe import
def _load_tg():
    try:
        from tg_bot import tg_send
        return tg_send
    except Exception:
        return None

def utc_now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def coalesce(x, default):
    return x if x is not None else default

def veto_and_merge(signal, agent):
    """Re-apply veto for safety and merge useful fields."""
    # starting point = agent view
    out = {
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "utc_time": signal.get("utc_time"),
        "price": signal.get("price"),
        "score16": signal.get("score16"),
        "score6": signal.get("score6"),
        "pre_action": signal.get("action"),
        "final_action": agent.get("final_action"),
        "confidence": agent.get("confidence"),
        "why": agent.get("why", []),
        "risks": agent.get("risks", []),
        "levels": agent.get("levels", {"support": [], "resistance": []}),
        "commentary": agent.get("commentary", ""),
        "source": signal.get("src", signal.get("source", "TD")),
    }

    # Soft safety: if agent omitted final_action, fall back to WAIT
    if out["final_action"] not in ("BUY", "SELL", "WAIT"):
        out["final_action"] = "WAIT"

    # Hard veto rules (mirror of the agent prompt)
    risk_text = " ".join([str(r).lower() for r in out["risks"]])
    if ("stale" in risk_text) or ("no atr plan" in risk_text):
        out["final_action"] = "WAIT"
    try:
        score16 = int(coalesce(out["score16"], 0))
        conf = int(coalesce(out["confidence"], 1))
    except Exception:
        score16, conf = 0, 1
    if score16 < 5 and conf <= 2:
        out["final_action"] = "WAIT"

    return out

def render_md(merged):
    # Pretty markdown-like block (we keep html=False for Telegram)
    sym = merged.get("symbol", "?")
    tf  = merged.get("timeframe", "?")
    action = merged.get("final_action", "WAIT")
    price = merged.get("price")
    s16 = merged.get("score16", 0)
    s6  = merged.get("score6", 0)
    why = merged.get("why", [])
    risks = merged.get("risks", [])
    lvls = merged.get("levels", {"support": [], "resistance": []})
    comm = merged.get("commentary", "")
    src = merged.get("source", "TD")
    built = merged.get("utc_time") or utc_now_iso()

    lines = []
    lines.append(f"🧭 #{sym.replace('=X','').replace('/','')}")
    lines.append(f"*{sym}* — *{action}* (Score {s16}/16 + {s6}/6) | TF *{tf}*")
    lines.append("")
    lines.append(f"🕰 Timeframe: *{tf}* | Source: `{src}`")
    if price is not None:
        lines.append(f"💰 Price: `{price}`")
    lines.append(f"🇮🇹 Score16/6: `{s16}` / `{s6}`")
    lines.append("— — — — — — — —")
    lines.append("")
    if comm:
        lines.append(f"🗣 *Commentary*: {comm}")
        lines.append("")
    lines.append("📌 *Why (rules)*:")
    if why:
        for w in why[:8]:
            lines.append(f"• {w}")
    else:
        lines.append("• n/a")

    # Levels (optional section)
    sup = lvls.get("support") or []
    res = lvls.get("resistance") or []
    if sup or res:
        lines.append("")
        lines.append("📏 *Levels*:")
        if sup:
            lines.append("• Support: " + ", ".join(map(str, sup[:5])))
        if res:
            lines.append("• Resistance: " + ", ".join(map(str, res[:5])))

    if risks:
        lines.append("")
        lines.append("⚠️ *Risks*:")
        for r in risks[:6]:
            lines.append(f"• {r}")

    lines.append("")
    lines.append(f"🕓 Built: `{built}`")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Render Claude/Grok agent JSON + original signal JSON")
    ap.add_argument("--signal", required=True, help="signal.json produced by main.py")
    ap.add_argument("--agent", required=True, help="agent.json returned by Claude/Grok")
    ap.add_argument("--send", action="store_true", help="send to Telegram using tg_bot.py")
    args = ap.parse_args()

    signal = load_json(Path(args.signal))
    agent  = load_json(Path(args.agent))
    merged = veto_and_merge(signal, agent)
    msg = render_md(merged)
    print(msg)

    if args.send:
        tg_send = _load_tg()
        if tg_send:
            try:
                ok = bool(tg_send(msg, html=False))
                print("📨 Telegram:", "sent ✅" if ok else "failed ❌")
            except Exception as e:
                print("Telegram send error:", e)
        else:
            print("Telegram module not available; printed only.")

if __name__ == "__main__":
    main()
