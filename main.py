from __future__ import annotations
import os, logging, html, json
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from analyst import make_signal, INSTRUMENTS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

FOREX = INSTRUMENTS[:8]
COMMS = INSTRUMENTS[8:]

def fmt_sig_html(sig: dict) -> str:
    esc = html.escape
    support = ", ".join(esc(str(x)) for x in sig["levels"]["support"])
    resistance = ", ".join(esc(str(x)) for x in sig["levels"]["resistance"])
    return (
        f"📊 <b>{esc(sig['pair'])}</b>\n"
        f"Price: {esc(f'{sig['price']:.4f}')} ({esc(sig['ts'])})\n"
        f"Score: {esc(f'{sig['score']:.2f}')} (Tech {sig['tech']}/16 + Macro {sig['macro']}/6)\n"
        f"Bias: {esc(sig['bias'])}\n"
        f"Action: <b>{esc(sig['action'])}</b> ({esc(sig['confidence'])})\n"
        f"Reason: {esc(sig['reason'])}\n"
        f"Support: {esc(support)}\n"
        f"Resistance: {esc(resistance)}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 TomaMobileForexBot ready! Use /menu for categories or /help for commands.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "/start - Greet the bot\n"
        "/status - Check bot status\n"
        "/menu - Select category and pair\n"
        "/scan - Scan all pairs for signals\n"
        "/analyze <PAIR> - Detailed analysis\n"
        "/signal <PAIR> - Quick signal\n"
        "/debug - Return EURUSD raw JSON"
    )
    await update.message.reply_text(msg)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot running on Termux.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💱 Forex", callback_data="cat:forex")],
        [InlineKeyboardButton("🛢 Commodities", callback_data="cat:comms")],
    ]
    await update.message.reply_text("Select category:", reply_markup=InlineKeyboardMarkup(kb))

async def on_cat_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        cat = q.data.split(":")[1]
        if cat == "forex":
            buttons = [[InlineKeyboardButton(p, callback_data=f"pair:{p}")] for p in FOREX]
            text = "Select Forex pair:"
        else:
            buttons = [[InlineKeyboardButton(p, callback_data=f"pair:{p}")] for p in COMMS]
            text = "Select commodity:"
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        log.exception("on_cat_choice error")
        await q.edit_message_text("<pre>on_cat_choice crashed — see logs</pre>", parse_mode=ParseMode.HTML)

async def on_pair_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        pair = q.data.split(":")[1]
        sig = make_signal(pair)
        await q.edit_message_text(fmt_sig_html(sig), parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("on_pair_choice error")
        await q.edit_message_text(f"<b>Analyze error</b>\n<pre>{html.escape(str(e))}</pre>", parse_mode=ParseMode.HTML)

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /analyze <PAIR>")
        return
    try:
        pair = context.args[0].upper()
        sig = make_signal(pair)
        await update.message.reply_text(fmt_sig_html(sig), parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("analyze_cmd error")
        await update.message.reply_text(f"<b>Analyze error</b>\n<pre>{html.escape(str(e))}</pre>", parse_mode=ParseMode.HTML)

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /signal <PAIR>")
        return
    try:
        pair = context.args[0].upper()
        sig = make_signal(pair)
        msg = f"{html.escape(sig['pair'])}: <b>{html.escape(sig['action'])}</b> ({html.escape(sig['confidence'])})\nScore: {sig['score']:.2f}\nReason: {html.escape(sig['reason'])}"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("signal_cmd error")
        await update.message.reply_text(f"<b>Signal error</b>\n<pre>{html.escape(str(e))}</pre>", parse_mode=ParseMode.HTML)

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lines = []
        for pair in INSTRUMENTS:
            sig = make_signal(pair)
            lines.append(f"{pair}: {sig['action']} ({sig['confidence']}), score {sig['score']:.2f}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        log.exception("scan_cmd error")
        await update.message.reply_text(f"<b>Scan error</b>\n<pre>{html.escape(str(e))}</pre>", parse_mode=ParseMode.HTML)

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sig = make_signal("EURUSD")
        await update.message.reply_text(f"<pre>{html.escape(json.dumps(sig, indent=2))}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        log.exception("debug_cmd error")
        await update.message.reply_text(f"<pre>{html.escape(str(e))}</pre>", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).pool_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("debug", debug_cmd))
    app.add_handler(CallbackQueryHandler(on_cat_choice, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(on_pair_choice, pattern="^pair:"))
    log.info("Bot polling...")
    app.run_polling(timeout=60, poll_interval=1)

if __name__ == "__main__":
    main()
