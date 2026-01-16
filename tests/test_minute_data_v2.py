import akshare as ak
import pandas as pd
from datetime import datetime

def test_minute_history_params():
    symbol = "300059"
    start_date = "2025-11-01 09:30:00"
    end_date = "2026-01-15 15:00:00"
    
    print(f"Testing parameterized minute fetch for {symbol}...")
    try:
        # Some versions use start_date="YYYY-MM-DD HH:MM:SS"
        # Note: akshare interface varies. Let's try standard 'start_date' arg if it exists.
        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', start_date=start_date, end_date=end_date, adjust='qfq')
        print(f"Fetched {len(df)} rows.")
        if not df.empty:
            print("Start:", df['时间'].iloc[0])
            print("End:  ", df['时间'].iloc[-1])
    except Exception as e:
        print(f"Error with start_date: {e}")

if __name__ == "__main__":
    test_minute_history_params()
