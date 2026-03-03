import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.strategy import analyze_volume_profile_strategy

def test_risk_control_position_limit():
    # Test that AI strategy is constrained by capital limit
    # Dummy volume profile
    import pandas as pd
    vp = pd.DataFrame({
        'price_bin': [9.0, 10.0, 11.0],
        '成交量': [1000, 5000, 2000]
    })
    
    current_price = 10.0
    total_capital = 10000.0  # limit 10k
    risk_pct = 0.05
    
    # Run strategy without any position
    res = analyze_volume_profile_strategy(
        current_price, vp, total_capital, risk_pct, current_shares=0, proximity_threshold=0.03
    )
    
    # We expect some recommendation
    assert res['signal'] in ["买入", "卖出", "观望", "持股"]
    
    # Force max position
    res_max = analyze_volume_profile_strategy(
        current_price, vp, total_capital, risk_pct, current_shares=1000, proximity_threshold=0.03
    )
    
    # Since we hold 1000 shares * 10 = 10k, we are at capital limit
    assert res_max['quantity'] <= 0
    assert "限制" in res_max.get('reason', '') or res_max['quantity'] == 0

def test_risk_control_stop_loss():
    import pandas as pd
    vp = pd.DataFrame({
        'price_bin': [5.0, 10.0, 15.0],
        '成交量': [0, 5000, 0]
    })
    
    current_price = 8.0 # Dropped below the major support at 10.0
    total_capital = 100000.0
    risk_pct = 0.02
    
    res = analyze_volume_profile_strategy(
        current_price, vp, total_capital, risk_pct, current_shares=1000, proximity_threshold=0.03
    )
    
    # Should suggest stop loss or sell due to breakdown
    assert res['signal'] in ["卖出", "观望"]
    assert "支撑" in res.get('reason', '') or "距离" in res.get('reason', '') or res['quantity'] <= 0
