"""
Analyst.py — safe, dependency-free analyzer for the bot.

Design goals:
- Never raise KeyError (always return a complete shape with 'score').
- Work even without live data (offline fallback), so the bot replies reliably.
- Single-file, no external imports beyond stdlib.
"""

from typing import Dict, Any

DEFAULT_LEVELS = {
    "support": [1.0800, 1.0750, 1.0700],
    "resistance": [1.0900, 1.0950, 1.1000],
}

def _shape() -> Dict[str, Any]:
    """Return a fully-populated analysis skeleton."""
    return {
        "pair": "EURUSD",
        "score": 0.0,               # ALWAYS present
        "bias": "neutral",          # neutral/bullish/bearish
        "summary": "Fallback analysis (no live data connected).",
        "events": [],               # list of {time, source, title, impact, sentiment}
        "levels": DEFAULT_LEVELS.copy(),
        "confidence": "low",        # low/medium/high
        "notes": [],
    }

def analyze_24h(pair: str = "EURUSD") -> Dict[str, Any]:
    """
    Produce a safe 24h analysis dict.
    This version uses a simple heuristic so it never fails offline.
    """
    data = _shape()
    data["pair"] = pair

    # --- simple, deterministic heuristic so bot always answers ---
    # If pair contains "USD" as base (endswith "USD"), lean bullish USD (= bearish pair)
    # If pair startswith "EUR", lean mild bullish EURUSD.
    bias_score = 0.0
    pair_up = pair.upper()

    if pair_up.startswith("EUR"):
        bias_score += 0.2
        data["notes"].append("EUR as base → slight bullish bias.")
    if pair_up.endswith("USD"):
        # If USD is quote (like EURUSD), USD weakness boosts pair (bullish)
        bias_score += 0.2
        data["notes"].append("USD as quote → slight bullish for the pair.")
    if "JPY" in pair_up:
        data["notes"].append("JPY pairs can be choppy; keep risk tight.")

    # Clamp and map to labels
    if bias_score > 0.25:
        data["bias"] = "bullish"
    elif bias_score < -0.25:
        data["bias"] = "bearish"
    else:
        data["bias"] = "neutral"

    # Convert bias to a 0..1 score (neutral ~0.5)
    data["score"] = round(0.5 + max(-0.5, min(0.5, bias_score)), 2)

    # Friendly summary
    data["summary"] = (
        f"{pair} bias: {data['bias']} | score={data['score']} "
        "(offline fallback; connect live data to refine)."
    )
    return data

def generate_signal(pair: str = "EURUSD") -> Dict[str, Any]:
    """
    Turn analysis into an actionable signal dict.
    Keys always present: action, confidence, reason, score, levels.
    """
    analysis = analyze_24h(pair)

    score = float(analysis.get("score", 0.5))  # safe default
    bias  = str(analysis.get("bias", "neutral"))
    levels = analysis.get("levels") or DEFAULT_LEVELS

    # Thresholds (tunable)
    if score >= 0.65:
        action = "BUY"
        reason = f"Bias {bias} with score {score} ≥ 0.65"
        conf = "medium" if score < 0.8 else "high"
    elif score <= 0.35:
        action = "SELL"
        reason = f"Bias {bias} with score {score} ≤ 0.35"
        conf = "medium" if score > 0.2 else "high"
    else:
        action = "HOLD"
        reason = f"Mixed signals; score {score} near neutral"
        conf = "low"

    return {
        "pair": pair,
        "action": action,
        "confidence": conf,
        "reason": reason,
        "score": score,
        "levels": levels,
        "analysis": analysis,   # include full blob for handlers to format
    }
