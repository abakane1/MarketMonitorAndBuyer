
import akshare as ak
import pandas as pd
import sys
import os

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_fetcher import get_stock_fund_flow_history

def test_fund_flow():
    symbol = "600076"
    print(f"Testing Fund Flow for {symbol}...")
    
    # 1. Direct API
    print("\n--- Direct API Call (ak.stock_individual_fund_flow) ---")
    try:
        df_api = ak.stock_individual_fund_flow(stock=symbol, market="sh")
        print(f"API Returned Shape: {df_api.shape}")
        if not df_api.empty:
            print(df_api.tail(5))
        else:
            print("API returned Empty DataFrame")
    except Exception as e:
        print(f"API Call Failed: {e}")

    # 2. Wrapper
    print("\n--- Wrapper Call (get_stock_fund_flow_history) [CACHE TEST] ---")
    try:
        # Use Cache
        df_wrapper = get_stock_fund_flow_history(symbol, force_update=False)
        print(f"Wrapper Returned Shape: {df_wrapper.shape}")
        if not df_wrapper.empty:
            print(df_wrapper.tail(5))
            
            # Check for NaN in critical columns
            print("\nCritical Columns Check:")
            print(df_wrapper[['日期', '主力净流入-净额']].tail(5))
            
        else:
            print("Wrapper returned Empty DataFrame")
            
    except Exception as e:
        print(f"Wrapper Call Failed: {e}")

if __name__ == "__main__":
    test_fund_flow()
