import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def check_data_availability():
    symbol = "600519" # Moutai
    
    print("--- Checking Historical Daily Data ---")
    try:
        # Standard daily data
        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        df_daily = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")
        print("Daily Data Columns:", df_daily.columns.tolist())
        # Does it have 'Volume by Price'? Probably not.
    except Exception as e:
        print("Daily fetch failed:", e)

    print("\n--- Checking History Time/Minute Data (for Volume Profile calc) ---")
    try:
        # Fetching a specific day's minute data to see details
        # Akshare often has stock_zh_a_hist_min_em for current range
        # Is there historical minute data for specific past date?
        # usually stock_zh_a_hist_min_em returns recent data (count-based usually)
        pass
    except Exception as e:
        print("Minute fetch failed:", e)

    print("\n--- Checking Bill/Tick Data (Tick level) ---")
    try:
        # stock_zh_a_tick_tx_js might give tick data for a specific day
        # This is heavy, but would allow calculating volume by price
        test_date = datetime.now().strftime("%Y-%m-%d") # Today?
        # Note: Tick data often only available for *very* recent dates or requires different interface
        # df_tick = ak.stock_zh_a_tick_tx_js(symbol="sh600519") 
        pass
    except Exception as e:
        pass

if __name__ == "__main__":
    check_data_availability()
