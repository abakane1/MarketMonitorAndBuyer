import akshare as ak
import pandas as pd
import streamlit as st
import os
from typing import List, Dict, Optional
from utils.time_utils import is_trading_time

STOCK_LIST_PATH = "stock_data/stock_list.parquet"

def get_all_stocks_list(force_update: bool = False) -> pd.DataFrame:
    """
    Fetches the full list of A-share stocks plus 588 Science/Tech ETFs.
    Prioritizes local cache.
    """
    # 1. Try Load Local
    if not force_update and os.path.exists(STOCK_LIST_PATH):
        try:
            df = pd.read_parquet(STOCK_LIST_PATH)
            if not df.empty:
                return df
        except Exception:
            pass # Fallback to fetch
            
    # 2. Fetch from AkShare
    try:
        # 2a. Fetch Stocks
        df_stocks = ak.stock_zh_a_spot_em()
        df_stocks = df_stocks[['代码', '名称']]
        
        # 2b. Fetch ETFs (Fund Spot)
        # Note: This might be slower, so we do it only on force update or first load
        df_etfs = ak.fund_etf_spot_em()
        # Filter for 588 series (Science & Tech Innovation Board ETFs) as requested
        # User said "ETF类（588）"
        df_588 = df_etfs[df_etfs['代码'].str.startswith('588')].copy()
        df_588 = df_588[['代码', '名称']]
        
        # 2c. Merge
        # Drop duplicates just in case
        df_final = pd.concat([df_stocks, df_588], axis=0).drop_duplicates(subset=['代码'])
        
        # 3. Save to Local
        if not os.path.exists("stock_data"):
            os.makedirs("stock_data")
        df_final.to_parquet(STOCK_LIST_PATH)
        
        return df_final
    except Exception as e:
        print(f"Error fetching stock/etf list: {e}")
        # Return empty if both fail
        return pd.DataFrame(columns=['代码', '名称'])

@st.cache_data(ttl=5)
def get_etf_spot_cached() -> pd.DataFrame:
    """
    Cached version of fund_etf_spot_em (heavy call).
    Updates every 5 seconds (Trading Hours).
    """
    return ak.fund_etf_spot_em()

@st.cache_data(ttl=3600)
def get_etf_spot_long_cache() -> pd.DataFrame:
    """
    Long cached version for off-hours (1 hour TTL).
    """
    return ak.fund_etf_spot_em()

@st.cache_data(ttl=5)
def get_stock_spot_cached() -> pd.DataFrame:
    """
    Cached version of stock_zh_a_spot_em.
    """
    return ak.stock_zh_a_spot_em()

@st.cache_data(ttl=3600)
def get_stock_spot_long_cache() -> pd.DataFrame:
    """
    Long cached version for off-hours (1 hour TTL).
    """
    return ak.stock_zh_a_spot_em()

def get_stock_realtime_info(symbol: str) -> Optional[Dict]:
    """
    Fetches real-time snapshot for a single stock or ETF.
    Now includes OHLCV data.
    """
    try:
        # Check if ETF
        is_etf = symbol.startswith(('51', '588', '15'))
        
        target_df = None
        
        if is_etf:
            try:
                if is_trading_time():
                    target_df = get_etf_spot_cached()
                else:
                    target_df = get_etf_spot_long_cache()
            except:
                pass
        else:
            # Stock
            try:
                if is_trading_time():
                    target_df = get_stock_spot_cached()
                else:
                    target_df = get_stock_spot_long_cache()
            except:
                pass
                
        if target_df is not None and not target_df.empty:
            row = target_df[target_df['代码'] == symbol]
            if not row.empty:
                data = row.iloc[0]
                
                # Handle different column names between ETF and Stock APIs
                # ETF: 开盘价, 最高价, 最低价
                # Stock: 今开, 最高, 最低
                
                price = data.get('最新价', 0)
                open_p = data.get('开盘价', data.get('今开', 0))
                high_p = data.get('最高价', data.get('最高', 0))
                low_p = data.get('最低价', data.get('最低', 0))
                vol = data.get('成交量', 0)
                amt = data.get('成交额', 0)
                
                return {
                    'code': data['代码'],
                    'name': data['名称'],
                    'price': price,
                    'market_cap': data.get('总市值', 0),
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'volume': vol,
                    'amount': amt
                }

        # Fallback if cache fails (Old Method)
        # ... logic if needed, or just return None
        return None

    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return None

def get_stock_minute_data(symbol: str) -> pd.DataFrame:
    """
    Fetches intraday minute data for a stock or ETF.
    """
    try:
        # Strategy:
        # 1. If it looks like an ETF (51x, 588x, 15x), try ETF interface first
        # 2. If it fails or not ETF, try Stock interface
        
        is_etf = symbol.startswith(('51', '588', '15'))
        
        if is_etf:
            try:
                df = ak.fund_etf_hist_min_em(symbol=symbol, period='1', adjust='qfq')
                if not df.empty:
                    return df
            except:
                pass # Fall through to stock interface
        
        # Standard Stock Interface (also works for some funds)
        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='qfq')
        return df
        
    except Exception as e:
        print(f"Error fetching minute data for {symbol}: {e}")
        return pd.DataFrame()
