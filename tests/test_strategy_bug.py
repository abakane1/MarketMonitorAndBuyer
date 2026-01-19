
import sys
import os
import pandas as pd
sys.path.append(os.getcwd())

from utils.strategy import analyze_volume_profile_strategy

def test_negative_position_bug():
    print("Locked and loaded: Testing Strategy Bug...")
    
    # Mock Data
    current_price = 10.0
    # Create a volume profile that creates a support just below price to trigger BUY
    # Support at 9.9, Price 10.0. Diff 1%. Threshold default is 3%. -> BUY Signal.
    vol_data = {
        'price_bin': [9.9, 10.0, 10.5],
        '成交量': [10000, 100, 10000] # Peak at 9.9 (Support) and 10.5 (Resistance)
    }
    vol_profile = pd.DataFrame(vol_data)
    
    total_capital = 100000.0
    risk_per_trade = 0.02 # 2000 Risk Amount
    
    # Case 1: No holdings.
    # Stop Loss = 9.9 * 0.98 = 9.702.
    # Loss per share = |10.0 - 9.702| = 0.298
    # Max Shares = 2000 / 0.298 ~= 6711 shares.
    
    # Case 2: Excessive Holdings
    # If we already hold 10000 shares.
    # Target is 6700. Current is 10000.
    # Action = 6700 - 10000 = -3300.
    # BEFORE FIX: Should return -3300 (Negative Buy).
    # AFTER FIX: Should return 0.
    
    current_shares_excessive = 10000
    
    print(f"\nScenario: Price {current_price}, Support 9.9. Signal SHOULD be BUY.")
    print(f"User holds {current_shares_excessive} shares. Calculated Risk-Based Target is approx 6700.")
    print("Expectation: Strategy should NOT suggest selling (-3300) on a BUY signal.")
    
    result = analyze_volume_profile_strategy(
        current_price,
        vol_profile,
        total_capital,
        risk_per_trade,
        current_shares=current_shares_excessive,
        proximity_threshold=0.03
    )
    
    print("\n--- Result ---")
    print(f"Signal: {result['signal']}")
    print(f"Target Position: {result['target_position']}")
    print(f"Suggestion: {result['quantity']}")
    
    # New Expectation: 
    # Signal should be '持股' (Hold) because quantity is 0.
    if result['signal'] == "持股" and result['quantity'] == 0:
        print("\n[PASS] Logic Verified: Signal corrected to '持股' when quantity is 0.")
    elif result['signal'] == "买入" and result['quantity'] == 0:
         print("\n[FAIL] Logic Inconsistent: Signal is '买入' but Quantity is 0.")
    elif result['quantity'] < 0:
        print("\n[FAIL] Regression: Negative quantity returned.")
    else:
        print(f"\n[?] Unexpected result state: {result}")

if __name__ == "__main__":
    test_negative_position_bug()
