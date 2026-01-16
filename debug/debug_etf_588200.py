import akshare as ak
import pandas as pd

try:
    print("Fetching ETF spot data...")
    df = ak.fund_etf_spot_em()
    print(f"Total ETFs: {len(df)}")
    
    target = df[df['代码'] == '588200']
    if not target.empty:
        print("Found 588200:")
        print(target)
    else:
        print("588200 NOT FOUND in ak.fund_etf_spot_em()")
        
    # Also check if it works in history
    print("\nFetching history for 588200...")
    hist = ak.stock_zh_a_hist_min_em(symbol='588200', period='1')
    if not hist.empty:
        print(f"History data found: {len(hist)} rows")
    else:
        print("History data EMPTY")
        
except Exception as e:
    print(f"Error: {e}")
