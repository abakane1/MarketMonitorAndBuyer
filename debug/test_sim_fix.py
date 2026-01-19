
import pandas as pd
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from utils.sim_ui import run_simulation, load_backtest_data

def test_simulation_correction():
    print("Loading data for 600076...")
    try:
        # We need to simulate the streamlit cache data loading manually or just call the function if env allows
        # But load_backtest_data uses st.cache_data, which needs streamlit context.
        # We can just manually load files to mock the inputs for run_simulation.
        
        df = pd.read_parquet("stock_data/600076_minute.parquet")
        df['时间'] = pd.to_datetime(df['时间'])
        
        target_date = "2026-01-19"
        df_target = df[df['时间'].dt.date.astype(str) == target_date].copy().sort_values("时间").reset_index(drop=True)
        df_history = df[df['时间'].dt.date.astype(str) < target_date].copy().sort_values("时间").reset_index(drop=True)
        
        print(f"Target rows: {len(df_target)}")
        print(f"History rows: {len(df_history)}")
        
        if df_history.empty:
            print("ERROR: History is empty! Test cannot isValidly verify the fix.")
            return

    except Exception as e:
        print(f"Data load failed: {e}")
        return

    # Mock parameters
    current_cash = 150000.0
    current_shares = 26000
    prox_thresh = 0.03
    risk_pct = 0.02
    
    print("Starting simulation with static historical profile...")
    
    res_df, trades = run_simulation(
        data_target=df_target,
        data_history=df_history,
        init_cash=current_cash,
        init_shares=current_shares,
        init_cost=3.85,
        prox_thresh=prox_thresh,
        risk_pct=risk_pct
    )
    
    print(f"Simulation finished. Trades generated: {len(trades)}")
    
    if trades:
        print("Sample Trade:", trades[0])
        
    print("Done.")

if __name__ == "__main__":
    test_simulation_correction()
