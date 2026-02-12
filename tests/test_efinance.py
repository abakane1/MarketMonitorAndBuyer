
import efinance as ef
import pandas as pd
import time

stock_code = "600519"
etf_code = "513500"

print(f"Testing efinance version: {ef.__version__ if hasattr(ef, '__version__') else 'unknown'}")

print(f"\n1. Real-time Quote for {stock_code}...")
try:
    df = ef.stock.get_quote_snapshot([stock_code, etf_code])
    if not df.empty:
        print(f"Success. Columns: {df.columns.tolist()}")
        print(df[['代码', '名称', '最新价', '涨跌幅']].head())
    else:
        print("Returned empty dataframe")
except Exception as e:
    print(f"Failed: {e}")

print(f"\n2. Minute Data (1min) for {stock_code}...")
try:
    # get_quote_history(stock_codes, klt=1) -> klt=1 is 1 min
    # default returns dict of df if multiple codes, or single df if single code? 
    # Actually efinance usually takes list.
    df = ef.stock.get_quote_history(stock_code, klt=1)
    if not df.empty:
        print(f"Success. Rows: {len(df)}")
        print(df.tail(2))
    else:
        print("Empty DataFrame")
except Exception as e:
    print(f"Failed: {e}")

print(f"\n3. Daily History for {stock_code}...")
try:
    df = ef.stock.get_quote_history(stock_code, klt=101) # 101 is daily
    if not df.empty:
        print(f"Success. Rows: {len(df)}")
        print(df.tail(2))
    else:
        print("Empty DataFrame")
except Exception as e:
    print(f"Failed: {e}")

print(f"\n4. Fund Flow for {stock_code}...")
try:
    # get_money_flow(stock_codes)
    df = ef.stock.get_money_flow(stock_code)
    if not df.empty:
        print(f"Success. Rows: {len(df)}")
        print(df.tail(2))
    else:
        print("Empty DataFrame")
except Exception as e:
    print(f"Failed: {e}")

print("\n5. Bill Board (Longhu) if available...")
# Not critical, just checking.
