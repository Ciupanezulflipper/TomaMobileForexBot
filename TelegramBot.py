#!/usr/bin/env python3

-- coding: utf-8 --

import logging import asyncio import random import sqlite3 from telegram import Update from telegram.ext import ( Application, CommandHandler, ContextTypes )

=== CONFIG ===

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN" ADMIN_IDS = [123456789] DB_PATH = "signals.db"

=== LOGGING ===

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

=== DB INIT ===

def init_db(): with sqlite3.connect(DB_PATH) as conn: cursor = conn.cursor() cursor.execute(''' CREATE TABLE IF NOT EXISTS signals ( id INTEGER PRIMARY KEY, pair TEXT, score INTEGER, type TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP ) ''') conn.commit()

=== SIGNAL GENERATOR ===

def generate_signal(): pairs = ["EUR/USD", "GBP/JPY", "AUD/CAD", "USD/JPY"] types = ["BUY", "SELL"] return { "pair": random.choice(pairs), "score": random.randint(70, 100), "type": random.choice(types) }

=== CHECK ADMIN ===

def is_admin(user_id: int) -> bool: return user_id in ADMIN_IDS

=== COMMAND HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_admin(update.effective_user.id): await update.message.reply_text("❌ Unauthorized") return await update.message.reply_text("✅ Forex Bot ready. Use /analyze /alerts /history /remove_db")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_admin(update.effective_user.id): return signal = generate_signal() with sqlite3.connect(DB_PATH) as conn: cursor = conn.cursor() cursor.execute("INSERT INTO signals (pair, score, type) VALUES (?, ?, ?)", (signal['pair'], signal['score'], signal['type'])) conn.commit() msg = f"📊 {signal['pair']} | {signal['type']} | Score: {signal['score']}" await update.message.reply_text(msg)

async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_admin(update.effective_user.id): return with sqlite3.connect(DB_PATH) as conn: cursor = conn.cursor() cursor.execute("SELECT pair, score, type FROM signals WHERE score > 85 ORDER BY timestamp DESC LIMIT 5") rows = cursor.fetchall() if not rows: await update.message.reply_text("No high-score signals.") else: for row in rows: await update.message.reply_text(f"🚨 {row[0]} | {row[2]} | Score: {row[1]}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE): if not is_admin(update.effective_user.id): return with sqlite3.connect(DB_PATH) as conn: cursor = conn.cursor() cursor.execute("SELECT pair, score, type, timestamp FROM signals ORDER BY timestamp DESC LIMIT 5") rows = cursor.fetchall() for row in rows: await update.message.reply_text(f"{row[3]} - {row[0]} {row[2]} ({row[1]})")

async def remove_db(update: Update, context: ContextTypes.DEFAULT_TYPE): import os if not is_admin(update.effective_user.id): return if os.path.exists(DB_PATH): os.remove(DB_PATH) await update.message.reply_text("🗑️ Database removed.") else: await update.message.reply_text("No database found.")

=== MAIN ===

async def main(): init_db() app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("analyze", analyze))
app.add_handler(CommandHandler("alerts", alerts))
app.add_handler(CommandHandler("history", history))
app.add_handler(CommandHandler("remove_db", remove_db))

logger.info("Bot running...")
await app.run_polling()

if name == 'main': try: asyncio.run(main()) except KeyboardInterrupt: print("\nBot stopped")


