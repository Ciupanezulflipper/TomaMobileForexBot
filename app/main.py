import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

def fetch_data(symbol='EURUSD=X', interval='1h', period='2d'):
    data = yf.download(tickers=symbol, interval=interval, period=period)
    return data.dropna()

def analyze(data):
    data['ema9'] = EMAIndicator(close=data['Close'], window=9).ema_indicator()
    data['ema21'] = EMAIndicator(close=data['Close'], window=21).ema_indicator()
    data['rsi'] = RSIIndicator(close=data['Close'], window=14).rsi()

    last = data.iloc[-1]
    if last['ema9'] > last['ema21'] and last['rsi'] < 70:
        return "📈 BUY Signal"
    elif last['ema9'] < last['ema21'] and last['rsi'] > 30:
        return "📉 SELL Signal"
    else:
        return "⏳ WAIT"

if __name__ == '__main__':
    df = fetch_data()
    signal = analyze(df)
    print(f"✅ Signal for EUR/USD: {signal}")
