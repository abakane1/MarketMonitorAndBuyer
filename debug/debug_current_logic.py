import akshare as ak
import pandas as pd

def get_stock_realtime_info_debug(symbol: str):
    print(f"DEBUG: Processing {symbol}")
    try:
        # Check if ETF
        is_etf = symbol.startswith(('51', '588', '15'))
        print(f"DEBUG: is_etf={is_etf}")
        
        if is_etf:
            try:
                print("DEBUG: Calling fund_etf_spot_em...")
                df = ak.fund_etf_spot_em()
                # print("DEBUG: df columns:", df.columns)
                # print("DEBUG: df head:", df.head())
                
                row = df[df['代码'] == symbol]
                if not row.empty:
                    print("DEBUG: Found row")
                    data = row.iloc[0]
                    return {
                        'code': data['代码'],
                        'name': data['名称'],
                        'price': data['最新价'],
                        'market_cap': data['总市值'],
                    }
                else:
                    print("DEBUG: Row not found in ETF spot")
            except Exception as e:
                print(f"ETF info fetch failed for {symbol}: {e}")
                pass

        print("DEBUG: Falling back to stock_individual_info_em")
        # Standard Stock
        df = ak.stock_individual_info_em(symbol=symbol)
        info_dict = dict(zip(df['item'], df['value']))
        
        return info_dict
    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return None

if __name__ == "__main__":
    get_stock_realtime_info_debug("588200")
