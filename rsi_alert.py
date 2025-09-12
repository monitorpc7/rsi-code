import ccxt
import pandas as pd
import pandas_ta as ta
import time
import os
from typing import Optional
from datetime import datetime

# Conditional import for Windows-specific sound library
try:
    import winsound
except ImportError:
    winsound = None

# --- Configuration ---
SYMBOL = 'XRP/USDT'
TIMEFRAME = '5m'  # Timeframe for analysis
RSI_PERIOD = 14
OVERBOUGHT_LEVEL = 70
OVERSOLD_LEVEL = 30
CHECK_INTERVAL_SECONDS = 1  # Check every second
ALERT_COOLDOWN_SECONDS = 300  # 5 minutes between same alerts

# --- Alert Sound Configuration ---
OVERBOUGHT_SOUND_FILE = 'overbought.wav'  # Must be a .wav file for winsound
OVERSOLD_SOUND_FILE = 'oversold.wav'    # Must be a .wav file for winsound

# --- Initialize Exchange for Perpetual Swaps ---
# The user requested perpetuals, which requires setting the 'defaultType' to 'swap'.
exchange = ccxt.mexc({
    'options': {
        'defaultType': 'swap',  # Use 'swap' for perpetuals, 'spot' for spot market
    },
})


def play_alert_sound(sound_file: str):
    """
    Plays a specified .wav sound file for an alert using winsound on Windows.
    Falls back to a system beep if the file is not found or on other OS.
    """
    try:
        # On Windows, use winsound to play the .wav file
        if os.name == 'nt' and winsound:
            if os.path.exists(sound_file):
                # Play the specified .wav file. SND_FILENAME flag is crucial.
                winsound.PlaySound(sound_file, winsound.SND_FILENAME)
            else:
                # If file is not found, print a warning and play a default beep
                print(f"\nWarning: Sound file not found at '{sound_file}'. Falling back to system beep.", flush=True)
                winsound.Beep(1000, 500)  # Fallback beep
        else:
            # For other operating systems (macOS, Linux), use a generic beep
            # as winsound is not available.
            print("\a", end='', flush=True)
    except Exception as e:
        print(f"\nCould not play alert sound '{sound_file}': {e}", flush=True)


def calculate_rsi(closes: pd.Series, period: int) -> Optional[float]:
    """
    Calculate RSI using pandas-ta library.
    :param closes: A pandas Series of closing prices.
    :param period: The lookback period for RSI.
    :return: The latest RSI value, or None if calculation is not possible.
    """
    if closes is None or len(closes) < period:
        return None

    # Calculate RSI using pandas-ta
    rsi_series = ta.rsi(close=closes, length=period)

    if rsi_series is None or rsi_series.empty:
        return None

    # Return the last calculated RSI value
    return rsi_series.iloc[-1]


def get_current_price(symbol: str) -> Optional[float]:
    """Fetches the last traded price for a symbol."""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Could not fetch current price for {symbol}: {e}")
        return None


def main():
    """Main function to run the RSI alert bot."""
    last_alert_type = None
    last_alert_time = 0

    print(f"--- Starting RSI Alert Bot for {SYMBOL} on MEXC Perpetuals ---")
    print(f"Timeframe: {TIMEFRAME}, RSI Period: {RSI_PERIOD}")
    print(f"Levels: Overbought > {OVERBOUGHT_LEVEL}, Oversold < {OVERSOLD_LEVEL}")
    print(f"Check Interval: {CHECK_INTERVAL_SECONDS}s, Alert Cooldown: {ALERT_COOLDOWN_SECONDS}s")
    print("-" * 20)

    while True:
        try:
            # Fetch more data to ensure indicator is "warmed up" and accurate
            limit = RSI_PERIOD * 10
            ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=limit)

            if not ohlcv or len(ohlcv) < RSI_PERIOD + 1:
                print(f"Warning: Not enough data for RSI. Found {len(ohlcv)} candles, need > {RSI_PERIOD + 1}.")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            # Create a pandas DataFrame for easier manipulation
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Calculate RSI
            current_rsi = calculate_rsi(df['close'], RSI_PERIOD)

            if current_rsi is None:
                print("Could not calculate RSI.")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            current_price = get_current_price(SYMBOL)
            price_str = f"{current_price:.4f}" if current_price is not None else "N/A"

            status_message = ""
            alert_to_fire = False
            current_alert_type = None

            if current_rsi > OVERBOUGHT_LEVEL:
                status_message = f"Overbought! RSI: {current_rsi:.2f} > {OVERBOUGHT_LEVEL}"
                current_alert_type = 'overbought'
                # Fire alert if it's a new condition or if cooldown has passed for the same condition
                if last_alert_type != 'overbought' or (time.time() - last_alert_time) > ALERT_COOLDOWN_SECONDS:
                    alert_to_fire = True

            elif current_rsi < OVERSOLD_LEVEL:
                status_message = f"Oversold! RSI: {current_rsi:.2f} < {OVERSOLD_LEVEL}"
                current_alert_type = 'oversold'
                # Fire alert if it's a new condition or if cooldown has passed for the same condition
                if last_alert_type != 'oversold' or (time.time() - last_alert_time) > ALERT_COOLDOWN_SECONDS:
                    alert_to_fire = True

            else:  # RSI is in neutral zone
                # Reset alert type when RSI is back to neutral, allowing a new alert if it crosses the threshold again
                last_alert_type = None

            timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            symbol_str = f"[{timestamp_str}] {SYMBOL} ({price_str}) - "

            if alert_to_fire:
                # Print the alert on a new line to preserve it in the console history
                print(f"\n*** ALERT *** {symbol_str}{status_message}", flush=True)

                sound_to_play = None
                if current_alert_type == 'overbought':
                    sound_to_play = OVERBOUGHT_SOUND_FILE
                elif current_alert_type == 'oversold':
                    sound_to_play = OVERSOLD_SOUND_FILE

                if sound_to_play:
                    play_alert_sound(sound_to_play)

                last_alert_time = time.time()
                last_alert_type = current_alert_type
            else:
                # Print normal status update
                final_status = status_message if status_message else f"RSI: {current_rsi:.2f}"
                # Combine status into a single line
                line_to_print = f"{symbol_str}{final_status}"
                # Use carriage return `\r` to move the cursor to the start of the line.
                # Pad with spaces (`<90`) to clear any characters from a previous, longer line.
                print(f"{line_to_print:<90}", end='\r', flush=True)

            time.sleep(CHECK_INTERVAL_SECONDS)

        except ccxt.NetworkError as e:
            print(f"A network error occurred: {e}. Retrying in {CHECK_INTERVAL_SECONDS}s...")
            time.sleep(CHECK_INTERVAL_SECONDS)
        except ccxt.ExchangeError as e:
            print(f"An exchange error occurred: {e}. Retrying in {CHECK_INTERVAL_SECONDS}s...")
            time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nScript interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Goodbye!")
            break


if __name__ == "__main__":
    main()