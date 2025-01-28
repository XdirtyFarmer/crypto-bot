import os
import time
import pandas as pd
import numpy as np
import telegram
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
from okx import MarketData, Account, Trade

# Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_API_KEY')
CHAT_ID = os.getenv('CHAT_ID')
OKX_API_KEY = os.getenv('OKX_API_KEY')
OKX_SECRET_KEY = os.getenv('OKX_SECRET_KEY')
OKX_PASSPHRASE = os.getenv('OKX_PASSPHRASE')

SYMBOLS = ['ETH-USDT', 'SOL-USDT', 'TRX-USDT', 'XRP-USDT']
TIMEFRAME = '15m'
INTERVAL = 60  # 1 jam

# Initialize OKX API
market = MarketData(OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, False)
trade = Trade(OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, False)

# Technical Indicators
def calculate_indicators(df):
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA50'] = df['close'].rolling(window=50).mean()
    df['RSI'] = calculate_rsi(df['close'], 14)
    df['MACD'], df['Signal'] = calculate_macd(df['close'])
    return df

def calculate_rsi(prices, period):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    return macd, signal_line

# Signal Generation
def generate_signals(df):
    signals = []
    
    # Trend Analysis
    trend = 'Bullish' if df['MA20'].iloc[-1] > df['MA50'].iloc[-1] else 'Bearish'
    
    # MACD Cross
    if df['MACD'].iloc[-2] < df['Signal'].iloc[-2] and df['MACD'].iloc[-1] > df['Signal'].iloc[-1]:
        signals.append('MACD Bullish Cross')
    elif df['MACD'].iloc[-2] > df['Signal'].iloc[-2] and df['MACD'].iloc[-1] < df['Signal'].iloc[-1]:
        signals.append('MACD Bearish Cross')
    
    # RSI Analysis
    if df['RSI'].iloc[-1] < 30:
        signals.append('RSI Oversold')
    elif df['RSI'].iloc[-1] > 70:
        signals.append('RSI Overbought')
    
    return signals, trend

# Risk Management
def calculate_risk_level(signals):
    risk_score = 0
    if 'MACD Bullish Cross' in signals:
        risk_score += 2
    if 'RSI Oversold' in signals:
        risk_score += 1
    return min(risk_score, 3)  # Scale 0-3

def generate_signal_message(symbol, signals, trend, df):
    last_close = df['close'].iloc[-1]
    atr = df['high'].iloc[-1] - df['low'].iloc[-1]
    
    message = f"🚨 **{symbol} Signal** 🚨\n"
    message += f"📊 Trend: {trend}\n"
    message += "🔍 Signals Detected:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
    
    entry = last_close
    stop_loss = entry - (atr * 1.5)
    take_profit = entry + (atr * 2)
    
    message += f"\n⚡ **Entry Area**: {entry:.4f}\n"
    message += f"🛑 **Stop Loss**: {stop_loss:.4f}\n"
    message += f"🎯 **Take Profit**: {take_profit:.4f}\n"
    
    return message

# Main Analysis Function
def analyze_markets():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    
    for symbol in SYMBOLS:
        try:
            # Get OHLCV Data
            data = market.get_candlesticks(instId=symbol, bar=TIMEFRAME, limit=100)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'vol'])
            df = df.apply(pd.to_numeric)
            
            # Calculate Indicators
            df = calculate_indicators(df)
            
            # Generate Signals
            signals, trend = generate_signals(df)
            
            if len(signals) > 0:
                # Create Signal Message
                message = generate_signal_message(symbol, signals, trend, df)
                
                # Send to Telegram
                bot.send_message(chat_id=CHAT_ID, 
                               text=message,
                               parse_mode='Markdown')
                
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

# Scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(analyze_markets, 'interval', minutes=INTERVAL)
    scheduler.start()

# Telegram Commands
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Crypto Scalping Bot Aktif! Sinyal akan dikirim setiap 1 jam")

# Main
if __name__ == '__main__':
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    
    start_scheduler()
    updater.start_polling()
    updater.idle()
