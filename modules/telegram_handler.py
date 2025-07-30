from dotenv import load_dotenv
load_dotenv()
# — TomaiSignalAI telegram handler —————————————
import os, asyncio, httpx, logging, re
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, Defaults   # ← fixed here
)

TD_KEY  = os.getenv("TWELVE_DATA_API_KEY")
FH_KEY  = os.getenv("FINNHUB_API_KEY")
BOT_TOK = os.getenv("TELEGRAM_BOT_TOKEN")

app = (
    Application
      .builder()
      .token(BOT_TOK)
      .defaults(Defaults(parse_mode="HTML"))
      .build()
)

# --------------------------------------------------------
async def _twelvedata_price(sym:str) -> float:
    url = f"https://api.twelvedata.com/price?symbol={sym}&apikey={TD_KEY}"
    async with httpx.AsyncClient(timeout=5) as cli:
        r = await cli.get(url)
    return float(r.json()["price"])

async def _finnhub_price(sym:str) -> float:
    url = f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FH_KEY}"
    async with httpx.AsyncClient(timeout=5) as cli:
        r = await cli.get(url)
    return float(r.json()["c"])

SYMBOL_MAP = {             # Forex ↔ API symbols
    "EURUSD": "EUR/USD",   # Twelve-Data uses “EUR/USD”
}
FH_PREFIX = "OANDA:"       # Finnhub wants “OANDA:EUR_USD”

async def get_price(sym:str) -> str:
    sym = sym.upper().replace("/","")
    td_sym = SYMBOL_MAP.get(sym, sym)
    try:
        p = await _twelvedata_price(td_sym)
    except Exception:
        fh_sym = FH_PREFIX + sym.replace("USD","_USD")
        p = await _finnhub_price(fh_sym)
    return f"{p:.5f}" if len(sym)==6 else f"{p:.2f}"

# -------- command handlers --------------------------------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online.\nSend /analyze EURUSD to test.")

async def analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /analyze EURUSD")
        return
    sym = ctx.args[0].upper()
    try:
        price = await get_price(sym)
        await update.message.reply_text(f"<b>{sym}</b> ⇒ {price}")
    except ValueError:
        await update.message.reply_text("⚠️ Unrecognised symbol")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

async def scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Scan coming soon…")

# register handlers
app.add_handler(CommandHandler("start",   start))
app.add_handler(CommandHandler("analyze", analyze))
app.add_handler(CommandHandler("scan",    scan))
