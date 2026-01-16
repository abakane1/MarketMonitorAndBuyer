import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def test_minute_history():
    symbol = "300059" # East Money (ChiNext example)
    print(f"Testing minute data fetch for {symbol}...")
    
    # Try fetching 1 minute data. AkShare docs usually imply 'stock_zh_a_hist_min_em' gets everything available or takes start/end?
    # Let's try with default args first to see range.
    try:
        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='qfq')
        print(f"Fetched {len(df)} rows.")
        if not df.empty:
            print("Start:", df['时间'].iloc[0])
            print("End:  ", df['时间'].iloc[-1])
            
            # Check range
            start_dt = datetime.strptime(str(df['时间'].iloc[0]), "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(str(df['时间'].iloc[-1]), "%Y-%m-%d %H:%M:%S")
            days = (end_dt - start_dt).days
            print(f"Date range covers approx {days} days.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_minute_history()
