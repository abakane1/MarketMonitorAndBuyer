import akshare as ak
import pandas as pd

def test_etf_info():
    symbol = "588200"
    print(f"Testing info for {symbol}...")
    try:
        # This is what's currently used
        df = ak.stock_individual_info_em(symbol=symbol)
        print("stock_individual_info_em result:")
        print(df)
    except Exception as e:
        print(f"stock_individual_info_em failed: {e}")

    print("\nTrying alternative: fund_etf_spot_em filtering...")
    try:
        # Alternative: get all spot data and filter
        df_all = ak.fund_etf_spot_em()
        row = df_all[df_all['代码'] == symbol]
        if not row.empty:
            print("Found in fund_etf_spot_em:")
            print(row.iloc[0])
        else:
            print("Not found in fund_etf_spot_em")
    except Exception as e:
        print(f"fund_etf_spot_em failed: {e}")

if __name__ == "__main__":
    test_etf_info()
