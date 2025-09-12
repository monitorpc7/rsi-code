def divergence_trade_setup(entry, direction, swing, atr):
    """
    ATR-based Trade Setup for RSI Divergence Scalping
    
    Parameters:
    -----------
    entry : float
        Your entry price.
    direction : str
        "long" or "short".
    swing : float
        For long = swing low, for short = swing high.
    atr : float
        ATR value (from 1m chart).
    
    Returns:
    --------
    dict with stop loss and TP levels
    """
    setup = {}

    if direction.lower() == "long":
        sl = swing - (0.5 * atr)
        tp1 = entry + (1.5 * atr)
        tp2 = entry + (3.0 * atr)

    elif direction.lower() == "short":
        sl = swing + (0.5 * atr)
        tp1 = entry - (1.5 * atr)
        tp2 = entry - (3.0 * atr)

    else:
        raise ValueError("Direction must be 'long' or 'short'")

    setup["Entry"] = round(entry, 6)
    setup["StopLoss"] = round(sl, 6)
    setup["TakeProfit1 (1.5 ATR)"] = round(tp1, 6)
    setup["TakeProfit2 (3 ATR)"] = round(tp2, 6)

    return setup


# -------------------------
# Example usage:
entry_price = float(input("Enter Entry Price: "))
direction = input("Direction (long/short): ")
swing = float(input("Enter Swing Low (for long) or Swing High (for short): "))
atr_value = float(input("Enter ATR Value: "))

trade = divergence_trade_setup(entry_price, direction, swing, atr_value)
print("\nTrade Setup:")
for k, v in trade.items():
    print(f"{k}: {v}")

