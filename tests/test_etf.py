import akshare as ak
import pandas as pd

def test_etf():
    print("Fetching ETF spot data...")
    try:
        # Common interface for ETFs
        df = ak.fund_etf_spot_em()
        print("Columns:", df.columns)
        print("Sample:", df.head())
        
        # Filter for 588 start
        etf_588 = df[df['代码'].str.startswith('588')]
        print(f"\nFound {len(etf_588)} ETFs starting with 588.")
        if not etf_588.empty:
            print(etf_588.head())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_etf()
