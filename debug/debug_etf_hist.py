import akshare as ak
import pandas as pd

def test_etf_history():
    symbol = "588200"
    print(f"Testing history for {symbol}...")
    try:
        # Try standard stock interface
        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='qfq')
        print("stock_zh_a_hist_min_em result:")
        print(df.head() if not df.empty else "Empty DataFrame")
    except Exception as e:
        print(f"stock_zh_a_hist_min_em failed: {e}")

    try:
        # Try ETF specific interface if exists?
        # Usually AkShare treats ETFs as stocks for minute data, but let's check
        pass
    except Exception as e:
        pass

if __name__ == "__main__":
    test_etf_history()
