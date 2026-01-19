import pandas as pd
import numpy as np
from typing import Dict, Tuple


def analyze_volume_profile_strategy(
    current_price: float, 
    vol_profile: pd.DataFrame, 
    total_capital: float, 
    risk_per_trade: float = 0.02,
    current_shares: int = 0,
    proximity_threshold: float = 0.03 # Default 3%
) -> Dict:
    """
    Analyzes Volume Profile to generate trading signals.
    
    Logic:
    1. Find High Volume Nodes (HVN) from profile.
    2. Nearest HVN below price = Support.
    3. Nearest HVN above price = Resistance.
    4. Signal:
       - If price is within proximity_threshold of Support -> BUY. Stop Loss = Support - 2%.
       - If price is within proximity_threshold of Resistance -> SELL. Stop Loss = Resistance + 2%.
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
    # Use STRICT inequality to avoid finding the current price bin as both support and resistance
    # If we are standing exactly on a massive volume node, we need to find the NEXT levels.
    df_below = vol_profile[vol_profile['price_bin'] < current_price]
    df_above = vol_profile[vol_profile['price_bin'] > current_price]
    
    support = 0.0
    resistance = float('inf')
    
    # Find Support (Strongest volume node strictly below)
    if not df_below.empty:
        support_row = df_below.loc[df_below['成交量'].idxmax()]
        support = support_row['price_bin']
    else:
        # Fallback: if no data below, use current or min
        support = current_price
        
    # Find Resistance (Strongest volume node strictly above)
    if not df_above.empty:
        resistance_row = df_above.loc[df_above['成交量'].idxmax()]
        resistance = resistance_row['price_bin']
    else:
        # Fallback: if no data above, use infinity or max?
        resistance = current_price # Means no resistance found above
        
    # 2. Determine Signal
    signal = "观望" # Wait
    stop_loss = 0.0
    reason = ""
    
    # Thresholds (Use argument)
    proximity_pct = proximity_threshold
    
    # Check Support Buy
    if support > 0 and (current_price - support) / current_price <= proximity_pct:
        signal = "买入"
        stop_loss = support * 0.98 # Stop below support
        diff_pct = ((current_price - support) / current_price) * 100
        reason = f"价格接近下方筹码支撑位 {support} (现价 {current_price}, 差距 {diff_pct:.2f}%)"
    
    # Check Resistance Sell
    elif resistance != float('inf') and (resistance - current_price) / current_price <= proximity_pct:
        signal = "卖出"
        # For Long-Only: Sell signal means exit now. 
        # Setting stop_loss to current_price to indicate immediate exit trigger.
        stop_loss = current_price 
        diff_pct = ((resistance - current_price) / current_price) * 100
        reason = f"价格接近上方筹码阻力位 {resistance} (现价 {current_price}, 差距 {diff_pct:.2f}%)"
        
    else:
        # Wait / Hold
        signal = "观望"
        # If holding, we need a guard. Use Support.
        if support > 0:
            stop_loss = support * 0.96 # Wider stop for holding
        
        # Calculate distance to nearest level for clear reason
        dist_supp = ((current_price - support) / current_price) * 100 if support > 0 else 999
        dist_res = ((resistance - current_price) / current_price) * 100 if resistance != float('inf') else 999
        
        reason = f"位于支撑 {support} (-{dist_supp:.2f}%) 与阻力 {resistance} (+{dist_res:.2f}%) 之间"

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
    
    # Fix: If BUY signal but we already have more shares than target, 
    # we should NOT suggest selling (negative action). We just don't buy more.
    if signal == "买入" and action_shares < 0:
        action_shares = 0
    
    # 4. Consistency Check: Sync Signal with Quantity
    # Logic: "Buy" signal MUST have positive quantity. If 0, it means "Hold" (full position).
    if signal == "买入" and action_shares == 0:
        signal = "持股"
        reason += " (仓位已满/风控限制)"
        
    # Logic: "Sell" signal should trigger exit. 
    # If we have no shares, we are just 'Watching'
    if signal == "卖出" and current_shares == 0:
        signal = "观望"
        action_shares = 0
    
    # Calculate Take Profit / Target
    take_profit = 0.0
    # Use original signal logic or current signal? 
    # If now "持股", we still want to see the Target (Take Profit). 
    # So we check if we are in "Buy" or "Hold" mode (Long bias).
    if signal in ["买入", "持股"]:
        # Target usually Resistance
        if resistance != float('inf'):
            take_profit = resistance
        else:
            # If no resistance above, maybe 1.5x risk
            risk_dist = current_price - stop_loss
            if risk_dist > 0:
                take_profit = current_price + (risk_dist * 2.0) # 2.0 R ratio
                
    elif signal in ["卖出", "观望"]:
        # Target usually Support
        if support > 0:
            take_profit = support
        else:
            risk_dist = stop_loss - current_price
            if risk_dist > 0:
                take_profit = current_price - (risk_dist * 2.0)
    
    return {
        "signal": signal,
        "current_price": current_price,
        "support": support,
        "resistance": resistance if resistance != float('inf') else "无",
        "stop_loss": round(stop_loss, 4),
        "take_profit": round(take_profit, 4) if take_profit > 0 else "N/A",
        "quantity": action_shares, # This is the DELTA (Bet Size)
        "target_position": target_position,
        "reason": reason
    }

