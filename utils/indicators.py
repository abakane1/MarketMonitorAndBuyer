import pandas as pd
import numpy as np

def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Calculates technical indicators for DeepSeek context.
    Indicators: MACD, RSI, KDJ, MA, Bollinger Bands.
    Expects df with columns: ['收盘', '最高', '最低'] (and sorted by time ascending usually).
    """
    if df.empty or len(df) < 30:
        return {}

    # Improve robustness: Ensure df is sorted by date/time ascending
    # Try to sort if '时间' exists
    if '时间' in df.columns:
        df = df.sort_values('时间', ascending=True).reset_index(drop=True)

    close = df['收盘'].astype(float)
    high = df['最高'].astype(float)
    low = df['最低'].astype(float)

    # 1. MA (Moving Averages)
    ma5 = close.rolling(window=5).mean().iloc[-1]
    ma10 = close.rolling(window=10).mean().iloc[-1]
    ma20 = close.rolling(window=20).mean().iloc[-1]

    # 2. RSI (Relative Strength Index) - 14 period
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs)).iloc[-1]

    # 3. MACD (12, 26, 9)
    # EMA12
    ema12 = close.ewm(span=12, adjust=False).mean()
    # EMA26
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = (macd_line - signal_line) * 2
    
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = macd_hist.iloc[-1]

    # 4. Bollinger Bands (20, 2)
    rolling_mean = close.rolling(window=20).mean()
    rolling_std = close.rolling(window=20).std()
    upper = rolling_mean + (rolling_std * 2)
    lower = rolling_mean - (rolling_std * 2)
    
    bb_upper = upper.iloc[-1]
    bb_mid = rolling_mean.iloc[-1] # Same as MA20
    bb_lower = lower.iloc[-1]

    # 5. KDJ (9, 3, 3) - Simple implementation
    low_min = low.rolling(window=9).min()
    high_max = high.rolling(window=9).max()
    rsv = (close - low_min) / (high_max - low_min) * 100
    
    # K, D, J initialization (using pandas ewm usually or iterative)
    # Simplified pandas appx:
    k = rsv.ewm(com=2, adjust=False).mean() # com=2 -> alpha=1/3
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    k_val = k.iloc[-1]
    d_val = d.iloc[-1]
    j_val = j.iloc[-1]

    # Construct Context String/Dict
    indicators = {
        "RSI(14)": round(rsi, 2),
        "MACD": f"DIF:{macd_val:.3f}, DEA:{signal_val:.3f}, Hist:{hist_val:.3f}",
        "KDJ": f"K:{k_val:.1f}, D:{d_val:.1f}, J:{j_val:.1f}",
        "MA": f"MA5:{ma5:.2f}, MA10:{ma10:.2f}, MA20:{ma20:.2f}",
        "Bollinger": f"Up:{bb_upper:.2f}, Mid:{bb_mid:.2f}, Low:{bb_lower:.2f}"
    }

    # Generate Interpretation (Pre-chewed for LLM)
    interpretations = []
    if rsi > 70: interpretations.append("RSI超买(>70)")
    elif rsi < 30: interpretations.append("RSI超卖(<30)")
    
    if hist_val > 0 and hist_val > macd_hist.iloc[-2]: interpretations.append("MACD红柱放大(强势)")
    elif hist_val < 0 and hist_val < macd_hist.iloc[-2]: interpretations.append("MACD绿柱放大(弱势)")
    elif (macd_line.iloc[-1] > signal_line.iloc[-1]) and (macd_line.iloc[-2] <= signal_line.iloc[-2]): interpretations.append("MACD金叉")
    elif (macd_line.iloc[-1] < signal_line.iloc[-1]) and (macd_line.iloc[-2] >= signal_line.iloc[-2]): interpretations.append("MACD死叉")

    if k_val > d_val and k.iloc[-2] <= d.iloc[-2]: interpretations.append("KDJ金叉")
    if k_val < d_val and k.iloc[-2] >= d.iloc[-2]: interpretations.append("KDJ死叉")

    indicators["signal_summary"] = " | ".join(interpretations) if interpretations else "无明显技术突变"
    
    return indicators
