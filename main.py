import ccxt
import time
import numpy as np
from datetime import datetime
import platform
import os
import winsound  # For Windows
import threading

# Initialize MEXC exchange
exchange = ccxt.mexc({
    'enableRateLimit': True,
})

# Configuration
symbols = ['XRP/USDT']  # Add your coins here
timeframe = '1m'  # Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
rsi_period = 14
price_lookback = 30  # Candles to analyze for divergence
min_peak_distance = 5  # Minimum candles between peaks
play_sounds = True  # Set to False to disable alert sounds

def play_bullish_alert():
    """Play sound for bullish divergence detection"""
    if not play_sounds:
        return
        
    system = platform.system()
    try:
        if system == 'Windows':
            winsound.Beep(880, 500)  # Higher pitch
            winsound.Beep(660, 500)
        elif system == 'Darwin':  # macOS
            os.system('afplay /System/Library/Sounds/Ping.aiff')
            time.sleep(0.5)
            os.system('afplay /System/Library/Sounds/Ping.aiff')
        elif system == 'Linux':
            os.system('spd-say "bullish divergence"')
        else:
            print('\a')  # System beep as fallback
            time.sleep(0.3)
            print('\a')
    except:
        print("Couldn't play sound")

def play_bearish_alert():
    """Play sound for bearish divergence detection"""
    if not play_sounds:
        return
        
    system = platform.system()
    try:
        if system == 'Windows':
            winsound.Beep(440, 500)  # Lower pitch
            winsound.Beep(330, 500)
        elif system == 'Darwin':  # macOS
            os.system('afplay /System/Library/Sounds/Basso.aiff')
        elif system == 'Linux':
            os.system('spd-say "bearish divergence"')
        else:
            print('\a')  # System beep
    except:
        print("Couldn't play sound")

def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    rsi = np.zeros_like(prices)
    rsi[:period] = 100.0 - 100.0 / (1 + avg_gain / (avg_loss + 1e-10))
    
    for i in range(period, len(prices)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i-1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i-1]) / period
        
        if avg_loss < 1e-10:
            rs = 100  # Prevent division by zero
        else:
            rs = avg_gain / avg_loss
            
        rsi[i] = 100.0 - 100.0 / (1 + rs)
    
    return rsi

def find_peaks(data, min_distance=5):
    peaks = []
    for i in range(min_distance, len(data)-min_distance):
        if data[i] == max(data[i-min_distance:i+min_distance+1]):
            peaks.append(i)
    return peaks

def detect_divergence(prices, rsi_values):
    # Find price peaks
    price_peaks = find_peaks(prices, min_peak_distance)
    rsi_peaks = find_peaks(rsi_values, min_peak_distance)
    
    bearish_divergences = []
    bullish_divergences = []
    
    # Check last two peaks for bearish divergence
    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        last_price_peak = price_peaks[-1]
        prev_price_peak = price_peaks[-2]
        last_rsi_peak = rsi_peaks[-1]
        prev_rsi_peak = rsi_peaks[-2]
        
        # Bearish divergence: Higher price highs with lower RSI highs
        if (prices[last_price_peak] > prices[prev_price_peak] and
            rsi_values[last_rsi_peak] < rsi_values[prev_rsi_peak]):
            bearish_divergences.append((prev_price_peak, last_price_peak))
    
    # Find troughs (reverse of peaks)
    price_troughs = find_peaks([-x for x in prices], min_peak_distance)
    rsi_troughs = find_peaks([-x for x in rsi_values], min_peak_distance)
    
    # Check last two troughs for bullish divergence
    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        last_price_trough = price_troughs[-1]
        prev_price_trough = price_troughs[-2]
        last_rsi_trough = rsi_troughs[-1]
        prev_rsi_trough = rsi_troughs[-2]
        
        # Bullish divergence: Lower price lows with higher RSI lows
        if (prices[last_price_trough] < prices[prev_price_trough] and
            rsi_values[last_rsi_trough] > rsi_values[prev_rsi_trough]):
            bullish_divergences.append((prev_price_trough, last_price_trough))
    
    return bullish_divergences, bearish_divergences

def monitor_divergences():
    print(f"Starting RSI Divergence Monitor ({timeframe})")
    print("=" * 50)
    
    while True:
        try:
            for symbol in symbols:
                # Fetch OHLCV data
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=price_lookback + rsi_period)
                if len(ohlcv) < price_lookback + rsi_period:
                    continue
                
                # Extract closing prices
                closes = np.array([x[4] for x in ohlcv])
                
                # Calculate RSI
                rsi = calculate_rsi(closes, rsi_period)
                valid_rsi = rsi[-price_lookback:]
                valid_prices = closes[-price_lookback:]
                
                # Detect divergences
                bullish, bearish = detect_divergence(valid_prices, valid_rsi)
                
                # Generate alerts
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if bullish:
                    print(f"\n🚀 BULLISH DIVERGENCE DETECTED ({symbol})")
                    print(f"Time: {timestamp} | TF: {timeframe}")
                    print(f"Price: {valid_prices[bullish[0][0]]:.4f} -> {valid_prices[bullish[0][1]]:.4f}")
                    print(f"RSI:   {valid_rsi[bullish[0][0]]:.2f} -> {valid_rsi[bullish[0][1]]:.2f}")
                    threading.Thread(target=play_bullish_alert).start()
                
                if bearish:
                    print(f"\n⚠️ BEARISH DIVERGENCE DETECTED ({symbol})")
                    print(f"Time: {timestamp} | TF: {timeframe}")
                    print(f"Price: {valid_prices[bearish[0][0]]:.4f} -> {valid_prices[bearish[0][1]]:.4f}")
                    print(f"RSI:   {valid_rsi[bearish[0][0]]:.2f} -> {valid_rsi[bearish[0][1]]:.2f}")
                    threading.Thread(target=play_bearish_alert).start()
            
            # Wait before next check (based on timeframe)
            sleep_time = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '30m': 1800,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400
            }.get(timeframe, 300)
            
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor_divergences()