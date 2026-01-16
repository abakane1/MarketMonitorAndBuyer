import akshare as ak
import pandas as pd

def verify():
    print("Verifying AkShare...")
    try:
        # Fetch real-time data for "600519" (Kweichow Moutai)
        # Note: API methods in AkShare change sometimes, but stock_zh_a_spot_em is a common one for real-time data
        print("Fetching spot data for A-shares...")
        df = ak.stock_zh_a_spot_em()
        
        # Filter for Moutai just to show it works
        moutai = df[df['代码'] == '600519']
        
        if not moutai.empty:
            print("Successfully fetched data for 600519 (Moutai):")
            print(moutai[['代码', '名称', '最新价', '涨跌幅', '成交量']].to_string(index=False))
        else:
            print("Fetched data, but could not find 600519. First 5 rows:")
            print(df.head()[['代码', '名称', '最新价']].to_string(index=False))
            
    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    verify()
