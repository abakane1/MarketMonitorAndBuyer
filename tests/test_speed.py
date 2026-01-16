import akshare as ak
import time

def test_speed():
    symbol = "600519"
    
    print(f"Testing individual fetch for {symbol}...")
    
    # Test 1: Minute data
    start = time.time()
    try:
        # Note: akshare symbols for minute data sometimes need prefix sometimes not. 
        # stock_zh_a_hist_min_em takes symbol code like '600519'
        df_min = ak.stock_zh_a_hist_min_em(symbol=symbol, period="1", adjust="qfq")
        print(f"Minute data fetch took: {time.time() - start:.2f}s")
        if not df_min.empty:
            print("Latest minute data:")
            print(df_min.tail(1).to_string(index=False))
    except Exception as e:
        print(f"Minute data failed: {e}")

    # Test 2: Spot data (full list) again? No, too slow.
    
    # Test 3: Bid/Ask data (Level 1 quote effectively)
    # stock_bid_ask_em might not exist or might change name. 
    # Let's try stock_zh_a_spot_em but that's the full list.
    
    # Is there a real-time quote for single stock? 
    # stock_individual_info_em(symbol="600519") -> basic info, not price?
    
    start = time.time()
    try:
        # This function fetches individual stock info, let's see if it has price
        info = ak.stock_individual_info_em(symbol=symbol)
        print(f"Individual info fetch took: {time.time() - start:.2f}s")
        print(info)
    except Exception as e:
        print(f"Individual info failed: {e}")

if __name__ == "__main__":
    test_speed()
