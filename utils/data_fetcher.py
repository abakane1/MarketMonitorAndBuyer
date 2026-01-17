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

STOCK_SPOT_PATH = "stock_data/stock_spot.parquet"
ETF_SPOT_PATH = "stock_data/etf_spot.parquet"

@st.cache_data(ttl=5)
def get_etf_spot_cached() -> pd.DataFrame:
    """
    Cached version of fund_etf_spot_em (heavy call).
    Updates every 5 seconds (Trading Hours).
    """
    return ak.fund_etf_spot_em()

def get_etf_spot_long_cache() -> pd.DataFrame:
    """
    Long cached version for off-hours (Using Local File).
    """
    should_fetch = is_trading_time() or not os.path.exists(ETF_SPOT_PATH)
    
    if should_fetch:
        try:
            df = ak.fund_etf_spot_em()
            if not df.empty:
                df.to_parquet(ETF_SPOT_PATH)
            return df
        except Exception as e:
            # Fallback to local if exists
            if os.path.exists(ETF_SPOT_PATH):
                return pd.read_parquet(ETF_SPOT_PATH)
            raise e
    else:
        return pd.read_parquet(ETF_SPOT_PATH)

@st.cache_data(ttl=5)
def get_stock_spot_cached() -> pd.DataFrame:
    """
    Cached version of stock_zh_a_spot_em.
    """
    return ak.stock_zh_a_spot_em()

def get_stock_spot_long_cache() -> pd.DataFrame:
    """
    Long cached version for off-hours (Using Local File).
    """
    should_fetch = is_trading_time() or not os.path.exists(STOCK_SPOT_PATH)
    
    if should_fetch:
        try:
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                df.to_parquet(STOCK_SPOT_PATH)
            return df
        except Exception as e:
            # Fallback to local if exists
            if os.path.exists(STOCK_SPOT_PATH):
                return pd.read_parquet(STOCK_SPOT_PATH)
            raise e
    else:
        return pd.read_parquet(STOCK_SPOT_PATH)

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

def aggregate_minute_to_daily(df: pd.DataFrame, precision: int = 2) -> str:
    """
    Aggregates minute-level data into a Daily OHLC summary string.
    Returns a formatted string table.
    """
    if df.empty:
        return "N/A"
        
    # Ensure datetime sorted
    if '时间' in df.columns:
        df = df.sort_values('时间')
        df['date'] = df['时间'].dt.date
    else:
        return "N/A (Time column missing)"
        
    # Aggegate
    # We need to manually aggregate because we want First Open, Max High, Min Low, Last Close
    daily = df.groupby('date').agg({
        '收盘': ['first', 'max', 'min', 'last'], # Open(approx), High, Low, Close
        '成交量': 'sum'
    })
    
    # Flatten columns
    daily.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Create compact string
    lines = []
    
    # Provide last 30 days to give sufficient context
    recent_daily = daily.tail(30)
    
    fmt = f".{precision}f"
    
    for date, row in recent_daily.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        # Format: Date: O=.., H=.., L=.., C=.., V=..
        line = (f"{date_str}: "
                f"O={row['open']:{fmt}}, "
                f"H={row['high']:{fmt}}, "
                f"L={row['low']:{fmt}}, "
                f"C={row['close']:{fmt}}, "
                f"V={int(row['volume'])}")
        lines.append(line)
        
    return "\n".join(lines)

FUND_FLOW_CACHE_PATH = "stock_data/fund_flow_cache.parquet"

def _get_fund_flow_cache() -> pd.DataFrame:
    """
    获取资金流向缓存数据。
    如果缓存不存在或不是今天的数据，则从 API 获取并保存。
    """
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    
    # 检查本地缓存是否存在且是今天的
    if os.path.exists(FUND_FLOW_CACHE_PATH):
        try:
            df = pd.read_parquet(FUND_FLOW_CACHE_PATH)
            # 检查缓存日期 (假设有 'cache_date' 列)
            if 'cache_date' in df.columns and not df.empty:
                cached_date = df['cache_date'].iloc[0]
                if str(cached_date) == today_str:
                    # 缓存有效，直接返回
                    return df
        except Exception as e:
            print(f"读取资金流向缓存失败: {e}")
    
    # 缓存不存在或过期，从 API 获取
    try:
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        if df is not None and not df.empty:
            # 清洗数据：将 '-' 替换为 NaN，并尝试转换为数值类型
            # 排除 '代码', '名称' 等明确的字符串列
            exclude_cols = ['代码', '名称']
            for col in df.columns:
                if col not in exclude_cols:
                    # 尝试转为数值，无法转换的（如 '-'）变为 NaN
                    # 这能解决 PyArrow 保存时的类型错误 ('-' vs double)
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    except:
                        pass # 保持原样

            # 添加缓存日期列
            df['cache_date'] = today_str
            # 保存到本地
            if not os.path.exists("stock_data"):
                os.makedirs("stock_data")
            df.to_parquet(FUND_FLOW_CACHE_PATH)
            return df
    except Exception as e:
        print(f"获取资金流向数据失败: {e}")
    
    return pd.DataFrame()

def get_stock_fund_flow(symbol: str) -> dict:
    """
    获取个股资金流向数据 (Fund Flow)。
    优先从本地缓存获取，缓存不存在或过期时从 API 获取并保存。
    """
    try:
        # 获取缓存数据 (自动处理过期逻辑)
        df = _get_fund_flow_cache()
        
        if df is None or df.empty:
            return {"error": "无数据"}
        
        # 筛选目标股票 (按代码匹配)
        target = df[df['代码'] == symbol]
        
        if target.empty:
            return {"error": f"未找到 {symbol} 的资金流向数据"}
        
        latest = target.iloc[0]
        
        def safe_format(val, divisor=10000):
            """安全格式化数值"""
            try:
                if pd.isna(val):
                    return "N/A"
                return f"{float(val) / divisor:.2f}万"
            except:
                return "N/A"
        
        def safe_pct(val):
            """安全格式化百分比"""
            try:
                if pd.isna(val):
                    return "N/A"
                return f"{float(val):.2f}%"
            except:
                return "N/A"
        
        # 安全获取最新价
        price_val = latest.get("最新价", "N/A")
        if pd.isna(price_val): 
            price_val = "N/A"
        
        result = {
            "名称": str(latest.get("名称", symbol)),
            "最新价": str(price_val),
            "涨跌幅": safe_pct(latest.get("今日涨跌幅", 0)),
            "主力净流入": safe_format(latest.get("今日主力净流入-净额", 0)),
            "主力净占比": safe_pct(latest.get("今日主力净流入-净占比", 0)),
            "超大单净流入": safe_format(latest.get("今日超大单净流入-净额", 0)),
            "大单净流入": safe_format(latest.get("今日大单净流入-净额", 0)),
        }
        
        return result
        
    except Exception as e:
        print(f"获取资金流向失败 {symbol}: {e}")
        return {"error": str(e)}



def get_price_precision(symbol: str) -> int:
    """
    Returns the number of decimal places for price display/calculation.
    ETFs (588, 51, 15) -> 3 decimals
    Stocks -> 2 decimals
    """
    if symbol.startswith(('588', '51', '15')):
        return 3
    return 2
