#!/usr/bin/env python3
import argparse, json, subprocess, sys, shlex, os
from datetime import datetime

def run_exporter(cmd_argv: list[str]) -> str:
    """Run your existing exporter and return its STDOUT (JSON string)."""
    try:
        p = subprocess.run(cmd_argv, check=True, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        # Bubble up exporter stderr so you can see API errors, etc.
        print(e.stderr.strip(), file=sys.stderr)
        raise
    # Also forward exporter’s stderr (warnings) to our stderr for visibility
    if p.stderr:
        print(p.stderr.strip(), file=sys.stderr)
    return p.stdout.strip()

def debug_line(payload: dict) -> str:
    tech = len(payload.get("technical_flags", {}) or {})
    fund = len(payload.get("fundamental_flags", {}) or {})
    src  = (payload.get("technical_meta", {}) or {}).get("src", "?")
    sym  = payload.get("symbol", "?")
    tf   = payload.get("timeframe", "?")
    ts   = payload.get("utc_build_time", datetime.utcnow().isoformat()+"Z")
    return f"[debug] {sym}/{tf} tech={tech} fund={fund} src={src} ts={ts}"

def main():
    ap = argparse.ArgumentParser(
        description="Wrapper that runs export_json_unified.py, prints debug to STDERR, and keeps JSON clean on STDOUT."
    )
    ap.add_argument("--exporter", default="export_json_unified.py",
                    help="Path to your existing exporter script (default: export_json_unified.py)")
    ap.add_argument("--symbol", required=True, help='Symbol, e.g. "EUR/USD", "TSLA"')
    ap.add_argument("--tf", type=int, required=True, help="Timeframe minutes, e.g. 5, 60, 240")
    ap.add_argument("--spread", type=float, default=1.2, help="Spread in pips to include (default: 1.2)")
    ap.add_argument("--outfile", default="", help="If set, also write JSON to this file")
    ap.add_argument("--stdout", action="store_true", help="Echo JSON to STDOUT (on by default if no outfile)")
    ap.add_argument("--extra", default="", help='Extra args to pass through to exporter (raw string)')
    args = ap.parse_args()

    # Build the command to run your real exporter
    cmd = ["python", args.exporter, "--symbol", args.symbol, "--tf", str(args.tf)]
    # pass spread only if your exporter supports it; harmless if ignored
    if "--spread" in open(args.exporter, "r", encoding="utf-8").read():
        cmd += ["--spread", str(args.spread)]
    if args.extra:
        cmd += shlex.split(args.extra)

    # Run exporter and parse JSON
    out = run_exporter(cmd)
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        print(f"[debug] JSON decode error: {e}", file=sys.stderr)
        print(out[:4000], file=sys.stderr)
        sys.exit(2)

    # Print a single debug line to STDERR
    print(debug_line(payload), file=sys.stderr)

    # Write JSON to file if requested
    if args.outfile:
        with open(args.outfile, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")

    # Print JSON to STDOUT if requested (or if no outfile was given)
    if args.stdout or not args.outfile:
        print(json.dumps(payload, ensure_ascii=False))

if __name__ == "__main__":
    main()
