
import efinance as ef
import pandas as pd

print("1. Testing Full Realtime Quotes (as Stock List)...")
try:
    # get_realtime_quotes() usually returns all stocks
    df = ef.stock.get_realtime_quotes()
    if not df.empty:
        print(f"Success. Fetched {len(df)} rows.")
        print(df.columns.tolist())
        print(df[['股票代码', '股票名称']].head())
        
        # Check if ETFs are included (e.g. 51xxxx)
        etfs = df[df['股票代码'].str.startswith('51')]
        print(f"ETFs (51xxxx) found: {len(etfs)}")
    else:
        print("Full quotes returned empty.")
except Exception as e:
    print(f"Full quotes failed: {e}")

print("\n2. Checking Fund Flow Columns in Realtime Quotes...")
if 'df' in locals() and not df.empty:
    # Check if fund flow related columns exist
    flow_cols = [c for c in df.columns if '流' in c or '净' in c]
    print(f"Potential Flow Columns: {flow_cols}")
    if flow_cols:
        print(df[flow_cols].head())

print("\n3. Testing Bill Board (Longhu) as fallback for flow? (Unlikely for realtime)")
# ...
