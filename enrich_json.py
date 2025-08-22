#!/usr/bin/env python3
# enrich_json.py — merge your exporter JSON + sentiment JSON
import json, argparse, sys
def deep_merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k,v in b.items():
            out[k] = deep_merge(out[k], v) if k in out else v
        return out
    return b
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out.json", help="your exporter JSON")
    ap.add_argument("--news", default="-", help="news JSON file or '-' for stdin")
    args = ap.parse_args()
    with open(args.base,"r",encoding="utf-8") as f: base = json.load(f)
    news = json.load(sys.stdin) if args.news=="-" else json.load(open(args.news,"r",encoding="utf-8"))
    print(json.dumps(deep_merge(base, news), ensure_ascii=False))
if __name__ == "__main__":
    main()
