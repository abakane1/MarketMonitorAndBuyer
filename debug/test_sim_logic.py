
import pandas as pd
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from utils.strategy import analyze_volume_profile_strategy

def test_simulation():
    print("Loading data...")
    try:
        df = pd.read_parquet("stock_data/600076_minute.parquet")
        df['时间'] = pd.to_datetime(df['时间'])
        target_date = "2026-01-19"
        df_target = df[df['时间'].dt.date.astype(str) == target_date].copy()
        df_target = df_target.sort_values("时间").reset_index(drop=True)
        print(f"Loaded {len(df_target)} rows for {target_date}")
    except Exception as e:
        print(f"Data load failed: {e}")
        return

    # Mock parameters
    current_cash = 150000.0
    current_shares = 26000
    prox_thresh = 0.03
    risk_pct = 0.02
    
    print("Starting loop...")
    trades = []
    
    for i in range(len(df_target)):
        # Limit loop for test speed if data is huge (minute data for 1 day is ~240 rows, fast enough)
        row = df_target.iloc[i]
        price = row['收盘']
        
        # Build Volume Profile
        current_data_slice = df_target.iloc[:i+1].copy()
        current_data_slice['price_bin'] = current_data_slice['收盘'].round(2)
        vol_profile = current_data_slice.groupby('price_bin')['成交量'].sum().reset_index()
        
        signal_out = analyze_volume_profile_strategy(
            current_price=price,
            vol_profile=vol_profile,
            total_capital=150000.0,
            risk_per_trade=risk_pct,
            current_shares=current_shares,
            proximity_threshold=prox_thresh
        )
        
        # Simple logging of logic execution
        if i % 60 == 0:
            print(f"Time: {row['时间']}, Price: {price}, Signal: {signal_out['signal']}")
            
    print("Simulation finished successfully.")

if __name__ == "__main__":
    test_simulation()
