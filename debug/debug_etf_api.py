import akshare as ak
import pandas as pd

def test_etf_min_specific():
    symbol = "588200"
    print(f"Testing ETF specific history for {symbol}...")
    try:
        # Some ETFs might use this? Or maybe it doesn't exist.
        # AkShare doesn't always have uniform naming, but let's try a few
        # 1. bond... no
        # 2. fund_etf_hist_min_em
        if hasattr(ak, 'fund_etf_hist_min_em'):
            print("Trying fund_etf_hist_min_em...")
            df = ak.fund_etf_hist_min_em(symbol=symbol, period='1', adjust='qfq')
            print(df.head())
        else:
            print("ak.fund_etf_hist_min_em does not exist.")
            
    except Exception as e:
        print(f"ETF specific fetch failed: {e}")

if __name__ == "__main__":
    test_etf_min_specific()
