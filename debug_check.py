#!/usr/bin/env python3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from analyst import _try_fetch_candles

load_dotenv()

def main():
    keys = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "FINNHUB_KEY": os.getenv("FINNHUB_KEY"),
        "TWELVE_DATA_API_KEY": os.getenv("TWELVE_DATA_API_KEY"),
        "ALPHA_VANTAGE_API_KEY": os.getenv("ALPHA_VANTAGE_API_KEY"),
    }
    print("API Key Check:")
    for k, v in keys.items():
        print(f"  {k}: {'Set' if v else 'Missing'}")

    print("\nSample fetch for EURUSD...")
    try:
        df, src = _try_fetch_candles("EURUSD")
        latest = df.index[-1]
        stale = (datetime.utcnow() - latest) > timedelta(hours=48)
        print(f"  Source     : {src}")
        print(f"  Last bar   : {latest} UTC")
        print(f"  Is stale   : {stale}")
        print(f"  Last close : {float(df['Close'].iloc[-1]):.5f}")
    except Exception as e:
        print(f"  Fetch error: {e}")

if __name__ == "__main__":
    main()
