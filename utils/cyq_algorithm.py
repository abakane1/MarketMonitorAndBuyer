# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from typing import Tuple, Dict

def calculate_cyq(daily_df: pd.DataFrame, current_price: float = None, price_bins: int = 100) -> Tuple[pd.DataFrame, Dict]:
    """
    Calculate the Chip Distribution (CYQ) based on historical daily data and turnover rate.
    
    Algorithm:
    1. Iterate through historical days.
    2. For each day, new chips (Volume) enter at that day's price range (High-Low).
    3. Existing chips decay by the Turnover Rate (换手率).
    4. S_t(P) = S_{t-1}(P) * (1 - Turnover_t) + Volume_t * Distribution_t(P)
    
    Args:
        daily_df: DataFrame containing Daily K-line data. 
                  Must have columns: '日期', '最高', '最低', '收盘', '成交量', '换手率'.
        current_price: Current market price (for calculating profit ratio). If None, uses last close.
        price_bins: Number of bins for the price histogram.
        
    Returns:
        (profile_df, metrics)
        profile_df: DataFrame with 'price', 'volume' columns.
        metrics: Dict with 'winner_ratio', 'avg_cost', etc.
    """
    if daily_df.empty:
        return pd.DataFrame(), {}
        
    # Ensure columns
    needed = ['日期', '最高', '最低', '收盘', '成交量', '换手率']
    for c in needed:
        if c not in daily_df.columns:
            # Try mapping some common alternatives
            if c == '换手率' and 'turnover' in daily_df.columns:
                daily_df = daily_df.rename(columns={'turnover': '换手率'})
            elif c == '换手率':
                # If missing turnover, estimate it? (Volume / Circulating Shares) - Hard without Circulating Shares
                # Fallback: Assume a small constant if missing (e.g. 1%) or try to infer.
                # For now return empty if critical data missing.
                return pd.DataFrame(), {'error': f"Missing column: {c}"}
            else:
                return pd.DataFrame(), {'error': f"Missing column: {c}"}

    df = daily_df.sort_values('日期').reset_index(drop=True)
    
    # 1. Setup Price Grid
    # We need a fixed price grid to accumulate chips.
    # Range: Min Low to Max High over history * some buffer
    min_p = df['最低'].min() * 0.8
    max_p = df['最高'].max() * 1.2
    
    if max_p <= min_p:
        return pd.DataFrame(), {'error': "Invalid Price Range"}
        
    # Create bin edges
    bin_size = (max_p - min_p) / price_bins
    price_grid = np.linspace(min_p, max_p, price_bins)
    
    # Initialize Chips Array (Volume at each price bin)
    chips = np.zeros(price_bins)
    
    # 2. Iterate History
    for idx, row in df.iterrows():
        vol = row['成交量']
        turnover = row['换手率'] # Expected in %, e.g., 1.5 means 1.5%
        
        # Normalize turnover to 0-1
        # Data usually comes as percent (0-100) or decimal (0-1)? 
        # Checking akshare typical output: usually percent (e.g. 2.55)
        # Safe check: if max turnover > 1, assume it's percent.
        # But we valid logic inside loop.
        
        # Let's assume standard percent data from AkShare
        decay = turnover / 100.0
        if decay > 1.0: decay = 1.0 # Cap at 100% turnover (rare but possible)
        
        # A. Decay existing chips
        chips = chips * (1 - decay)
        
        # B. Add new chips
        # Model: Uniform distribution between High and Low for the day
        # (Standard CYQ often uses Triangle, but Uniform is a good simplification)
        day_high = row['最高']
        day_low = row['最低']
        day_avg = row['收盘'] # Use Close as proxy for center mass if needed
        
        if day_high == day_low:
            # Single price point
            # Find bin index
            bin_idx = int((day_high - min_p) / bin_size)
            if 0 <= bin_idx < price_bins:
                chips[bin_idx] += vol
        else:
            # Distribute vol across bins covered by [Low, High]
            low_idx = int((day_low - min_p) / bin_size)
            high_idx = int((day_high - min_p) / bin_size)
            
            # Clip to valid range
            low_idx = max(0, min(low_idx, price_bins-1))
            high_idx = max(0, min(high_idx, price_bins-1))
            
            if high_idx >= low_idx:
                span = high_idx - low_idx + 1
                chips[low_idx : high_idx+1] += (vol / span)
                
    # 3. Compile Result
    profile_df = pd.DataFrame({
        'price': price_grid,
        'volume': chips
    })
    
    # Filter out near-zero bins
    profile_df = profile_df[profile_df['volume'] > (profile_df['volume'].sum() * 0.0001)] 
    
    # 4. Calculate Metrics
    current = current_price if current_price else df.iloc[-1]['收盘']
    
    total_chips = profile_df['volume'].sum()
    winner_chips = profile_df[profile_df['price'] < current]['volume'].sum()
    
    winner_ratio = (winner_chips / total_chips) if total_chips > 0 else 0
    
    # Average Cost
    avg_cost = (profile_df['price'] * profile_df['volume']).sum() / total_chips if total_chips > 0 else 0
    
    # concentration (90% range)
    # TODO: Calculate concentration if needed
    
    metrics = {
        'winner_ratio': winner_ratio,
        'avg_cost': avg_cost,
        'current_price': current,
        'total_chips': total_chips
    }
    
    return profile_df, metrics
