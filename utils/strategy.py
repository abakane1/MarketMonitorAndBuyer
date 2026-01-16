import pandas as pd
import numpy as np
from typing import Dict, Tuple

def analyze_volume_profile_strategy(
    current_price: float, 
    vol_profile: pd.DataFrame, 
    total_capital: float, 
    risk_per_trade: float = 0.02,
    current_shares: int = 0
) -> Dict:
    """
    Analyzes Volume Profile to generate trading signals.
    
    Logic:
    1. Find High Volume Nodes (HVN) from profile.
    2. Nearest HVN below price = Support.
    3. Nearest HVN above price = Resistance.
    4. Signal:
       - If price is within 1% of Support -> BUY. Stop Loss = Support - 2%.
       - If price is within 1% of Resistance -> SELL. Stop Loss = Resistance + 2%.
       - Else -> WAIT.
       
    Returns dict with keys: 'signal', 'support', 'resistance', 'stop_loss', 'quantity', 'reason'
    """
    if vol_profile.empty or current_price <= 0:
        return {"signal": "NODATA"}

    # Sort by volume to find peaks? Or just treat local peaks? 
    # Global Max Volume Price (POC - Point of Control)
    poc_row = vol_profile.loc[vol_profile['成交量'].idxmax()]
    poc_price = poc_row['price_bin']
    
    # Simple logic: Find meaningful peaks. 
    # For now, let's treat the POC as the main magnet.
    # But better: Iterate prices to find nearest strong levels.
    
    # 1. Separate profile into Above and Below current price
    df_below = vol_profile[vol_profile['price_bin'] < current_price]
    df_above = vol_profile[vol_profile['price_bin'] > current_price]
    
    support = 0.0
    resistance = float('inf')
    
    # Find Support (Strongest volume node below)
    if not df_below.empty:
        # We want the strongest level not too far away? 
        # Let's just take the max volume price below.
        support_row = df_below.loc[df_below['成交量'].idxmax()]
        support = support_row['price_bin']
        
    # Find Resistance (Strongest volume node above)
    if not df_above.empty:
        resistance_row = df_above.loc[df_above['成交量'].idxmax()]
        resistance = resistance_row['price_bin']
        
    # 2. Determine Signal
    signal = "观望" # Wait
    stop_loss = 0.0
    reason = ""
    
    # Thresholds (e.g., 2% proximity)
    proximity_pct = 0.03
    
    # Check Support Buy
    if support > 0 and (current_price - support) / current_price <= proximity_pct:
        signal = "买入"
        stop_loss = support * 0.98 # Stop below support
        reason = f"价格接近下方筹码支撑位 {support}"
    
    # Check Resistance Sell
    elif resistance != float('inf') and (resistance - current_price) / current_price <= proximity_pct:
        signal = "卖出"
        stop_loss = resistance * 1.02 # Stop above resistance
        reason = f"价格接近上方筹码阻力位 {resistance}"
        
    else:
        reason = f"位于支撑 {support} 与阻力 {resistance} 之间"

    # 3. Position Sizing
    # Max Loss Amount = Capital * Risk
    # Max Loss per Share = |Entry - StopLoss|
    # Quantity = Max Loss Amount / Max Loss per Share
    target_position = 0
    if signal == "买入" and stop_loss > 0:
        max_loss_amount = total_capital * risk_per_trade
        loss_per_share = abs(current_price - stop_loss)
        if loss_per_share > 0:
            target_position = int(max_loss_amount / loss_per_share)
            target_position = (target_position // 100) * 100
            
    elif signal == "卖出":
        target_position = 0 # Sell signal implies exit
        
    # Calculate Action (Delta)
    action_shares = target_position - current_shares
    
    # Round down to 100 for valid trade
    # If action is small (e.g. 50 shares), ignore or set to 0?
    # Keep it raw for now, logic can handle it.
    
    return {
        "signal": signal,
        "current_price": current_price,
        "support": support,
        "resistance": resistance if resistance != float('inf') else "无",
        "stop_loss": round(stop_loss, 4),
        "quantity": action_shares, # This is the DELTA (Bet Size)
        "target_position": target_position,
        "reason": reason
    }
