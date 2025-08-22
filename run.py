#!/usr/bin/env python3
import os, sys, pathlib, importlib.util

ROOT = pathlib.Path(__file__).resolve().parent

# --- 1) Make sure we are at project root
os.chdir(ROOT)

# --- 2) Ensure all likely module locations are importable
CANDIDATE_DIRS = [
    str(ROOT),
    str(ROOT / "gpt5_baseline"),
    str(ROOT / "gpt5_baseline" / "helpers"),
]
for d in CANDIDATE_DIRS[::-1]:  # prepend in this order
    if d not in sys.path:
        sys.path.insert(0, d)

# --- 3) Load .env (from ./ or ./gpt5_baseline)
from pathlib import Path
env_here = ROOT / ".env"
env_alt  = ROOT / "gpt5_baseline" / ".env"
dotenv_path = env_here if env_here.exists() else (env_alt if env_alt.exists() else None)
if dotenv_path:
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=str(dotenv_path))
        print(f"[env] loaded {dotenv_path}")
    except Exception as e:
        print(f"[env] WARN: could not load .env: {e}")

# --- 4) Import core robustly (by name then by location)
def import_core():
    try:
        import core  # noqa: F401
        return core
    except Exception:
        # Try direct file locations
        for p in [ROOT/"core.py", ROOT/"gpt5_baseline"/"core.py"]:
            if p.exists():
                spec = importlib.util.spec_from_file_location("core", str(p))
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                return mod
        raise ModuleNotFoundError("core.py not found in project root nor gpt5_baseline/")

core = import_core()

def main():
    import argparse
    ap = argparse.ArgumentParser(description="TomaMobileForexBot runner")
    ap.add_argument("symbol", help='e.g. "EUR/USD" or "USDJPY"')
    ap.add_argument("tf", type=int, help="timeframe minutes (5, 60, 240)")
    args = ap.parse_args()

    res = core.analyze_once(args.symbol, args.tf)
    from pprint import pprint
    pprint(res)

if __name__ == "__main__":
    main()
