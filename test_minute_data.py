# Test the Wrapper Function which contains the Fallback Logic
print("5. Testing Wrapper `get_stock_minute_data('588200')` (Should trigger fallback)...")
try:
    from utils.data_fetcher import get_stock_minute_data
    df = get_stock_minute_data("588200")
    print(f"Wrapper Result: {len(df)} rows.")
    if not df.empty:
        print(df.tail())
        print("Columns:", df.columns.tolist())
except Exception as e:
    print(f"Wrapper Failed: {e}")

print("-" * 20)
print("4. Testing Sina Source: stock_zh_a_minute(symbol='sh588200')...")
try:
    # Sina needs prefix usually
    df = ak.stock_zh_a_minute(symbol="sh588200", period='1')
    print(f"Sina Result: {len(df)} rows.")
    if not df.empty:
        print(df.tail())
except Exception as e:
    print(f"Sina Failed: {e}")
