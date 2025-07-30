import os, httpx, asyncio, json

TD_API = os.getenv("TWELVE_DATA_API_KEY")
FH_API = os.getenv("FINNHUB_API_KEY")

async def _get_json(url: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
    try:
        return r.json()
    except Exception:
        return {"error": "Bad JSON", "text": r.text}

async def get_price(symbol: str):
    """Return float price or str error."""
    # --- Twelve-Data first --------------------------------------------------
    if TD_API:
        td_symbol = symbol.replace("/", "")
        url = f"https://api.twelvedata.com/price?symbol={td_symbol}&apikey={TD_API}"
        data = await _get_json(url)
        if "price" in data and data["price"] not in (None, "error"):
            return float(data["price"])
    # --- Finnhub fallback ---------------------------------------------------
    if FH_API:
        fh_symbol = f"OANDA:{symbol.replace('/','_')}"
        url = f"https://finnhub.io/api/v1/quote?symbol={fh_symbol}&token={FH_API}"
        data = await _get_json(url)
        if "c" in data and data["c"]:
            return float(data["c"])
    return f"price-lookup-failed: {data.get('error', 'no data')}"
