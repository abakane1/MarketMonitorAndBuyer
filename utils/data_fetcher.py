import akshare as ak
import pandas as pd
import streamlit as st
import os
import logging
from typing import List, Dict, Optional
from utils.time_utils import is_trading_time
from datetime import datetime, time

# --- 日志配置 ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --- 自定义异常类 ---
class DataFetchError(Exception):
    """数据获取失败（网络/API 错误）"""
    pass


class DataParseError(Exception):
    """数据解析失败"""
    pass


class DataNotFoundError(Exception):
    """数据不存在"""
    pass


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
                logger.debug(f"从本地缓存加载股票列表: {len(df)} 条")
                return df
        except FileNotFoundError:
            logger.info("本地缓存文件不存在，将从 API 获取")
        except Exception as e:
            logger.warning(f"读取本地缓存失败: {type(e).__name__}: {e}")
            
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
    except ConnectionError as e:
        logger.error(f"网络连接失败: {e}")
        return pd.DataFrame(columns=['代码', '名称'])
    except KeyError as e:
        logger.error(f"API 返回数据缺少必要字段: {e}")
        return pd.DataFrame(columns=['代码', '名称'])
    except Exception as e:
        logger.error(f"获取股票/ETF 列表失败: {type(e).__name__}: {e}")
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
    
    # Extra Check: If file exists but is stale (not from today or before close)
    if not should_fetch:
         try:
             mtime = os.path.getmtime(ETF_SPOT_PATH)
             file_dt = datetime.fromtimestamp(mtime)
             now = datetime.now()
             
             # 1. File is from previous day -> fetch
             if file_dt.date() < now.date():
                 should_fetch = True
             # 2. Today is weekday, now > 15:05, but file < 15:00 -> fetch (get closing price)
             elif now.weekday() < 5 and now.time() > time(15, 5) and file_dt.time() < time(15, 0):
                 should_fetch = True
         except:
             should_fetch = True

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
    
    # Extra Check: If file exists but is stale
    if not should_fetch:
         try:
             mtime = os.path.getmtime(STOCK_SPOT_PATH)
             file_dt = datetime.fromtimestamp(mtime)
             now = datetime.now()
             
             # 1. File is from previous day -> fetch
             if file_dt.date() < now.date():
                 should_fetch = True
             # 2. Today is weekday, now > 15:05, but file < 15:00 -> fetch (get closing price)
             elif now.weekday() < 5 and now.time() > time(15, 5) and file_dt.time() < time(15, 0):
                 should_fetch = True
         except:
             should_fetch = True
    
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
                    'pre_close': data.get('昨收', price), # Fallback to current price if missing, but ideally pre_close
                    'market_cap': data.get('总市值', 0),
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'volume': vol,
                    'amount': amt
                }


        # --- Fallback: Use Minute Data (if Spot API fails) ---
        # If we reached here, spot fetch failed or returned empty.
        logger.warning(f"实时行情(Spot)获取失败，尝试使用分时数据回退: {symbol}")
        
        # Try to get Pre-Close from Daily History
        pre_close = 0.0
        try:
            # We need a way to get yesterday's close.
            # Use daily history API.
            # This is slow, so maybe cache it? 
            # ideally we should have a separate function for this.
            daily_df = get_stock_daily_history(symbol) 
            if not daily_df.empty:
                # daily_df should be sorted by date
                # If today is in df (market closed/trading), we want the row BEFORE today.
                # If today is NOT in df (market open), last row is yesterday.
                
                # Check last row date
                last_date_str = str(daily_df.iloc[-1]['日期'])
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                if last_date_str == today_str:
                    # Today is present, so pre_close is 2nd last row
                    if len(daily_df) >= 2:
                        pre_close = float(daily_df.iloc[-2]['收盘'])
                else:
                    # Last row is (presumably) yesterday
                    pre_close = float(daily_df.iloc[-1]['收盘'])
        except Exception as e_pc:
             logger.warning(f"获取昨日收盘价失败 {symbol}: {e_pc}")

        # 1. Fetch Minute Data
        try:
            min_df = get_stock_minute_data(symbol)
            if not min_df.empty:
                latest = min_df.iloc[-1]
                
                # ... (Name extraction) ...
                name = symbol
                try:
                    stock_list = get_all_stocks_list()
                    name_row = stock_list[stock_list['代码'] == symbol]
                    if not name_row.empty:
                        name = name_row.iloc[0]['名称']
                except:
                    pass
                
                # 3. Aggregate Day Stats
                price = float(latest['收盘'])
                
                # If pre_close failed above, fallback to Open price (better than current price)
                if pre_close <= 0:
                     if '开盘' in min_df.columns:
                         pre_close = float(min_df.iloc[0]['开盘']) # Rough approx if all else fails
                     else:
                         pre_close = price

                open_p = float(min_df.iloc[0]['开盘']) if '开盘' in min_df.columns else price
                high_p = float(min_df['最高'].max()) if '最高' in min_df.columns else price
                low_p = float(min_df['最低'].min()) if '最低' in min_df.columns else price
                vol = float(min_df['成交量'].sum()) if '成交量' in min_df.columns else 0
                
                return {
                    'code': symbol,
                    'name': name,
                    'price': price,
                    'pre_close': pre_close,
                    'market_cap': 0,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'volume': vol,
                    'amount': 0
                }
        except Exception as e_fallback:
            logger.error(f"分时数据回退失败 {symbol}: {e_fallback}")

        return None

    except Exception as e:
        logger.error(f"获取实时行情失败 {symbol}: {e}")
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
        logger.error(f"获取分时数据失败 {symbol}: {e}")
        return pd.DataFrame()

def get_stock_daily_history(symbol: str) -> pd.DataFrame:
    """
    Fetch daily history (last 30 days) to get Pre-Close.
    """
    try:
         # Try ETF
        is_etf = symbol.startswith(('51', '588', '15'))
        start_date = (datetime.now() - pd.Timedelta(days=30)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        
        if is_etf:
            try:
                # ak.fund_etf_hist_em(symbol="513500", period="daily", start_date="20000101", end_date="20230201", adjust="qfq")
                df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                if not df.empty: return df
            except: pass
            
        # Try Stock
        # ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20170301", end_date='20210907', adjust="qfq")
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        return df
    except Exception as e:
        logger.error(f"获取日线数据失败 {symbol}: {e}")
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

    return "\n".join(lines)

# FUND_FLOW_CACHE_PATH = "stock_data/fund_flow_cache.parquet" # DEPRECATED

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
            logger.warning(f"读取资金流向缓存失败: {e}")
    
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
        logger.error(f"获取资金流向数据失败: {e}")
    
    return pd.DataFrame()

def _get_market_code(symbol: str) -> str:
    """
    Indentify market code for AkShare fund flow API.
    sh: 6*, 9*
    sz: 0*, 3*
    bj: 4*, 8*
    """
    if symbol.startswith(('6', '9')):
        return 'sh'
    if symbol.startswith(('0', '3')):
        return 'sz'
    if symbol.startswith(('4', '8')):
        return 'bj'
    return 'sh' # Default fallback

FUND_FLOW_DIR = "stock_data/fund_flow"

def get_stock_fund_flow_history(symbol: str, force_update: bool = False) -> pd.DataFrame:
    """
    Fetch historical fund flow data for a single stock.
    Returns DataFrame with columns like: 日期, 收盘价, 主力净流入-净额, etc.
    """
    # Ensure directory
    if not os.path.exists(FUND_FLOW_DIR):
        os.makedirs(FUND_FLOW_DIR)
        
    cache_path = os.path.join(FUND_FLOW_DIR, f"{symbol}.parquet")
    
    should_fetch = True
    
    # 1. Check Cache
    if not force_update and os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            file_dt = datetime.fromtimestamp(mtime)
            now = datetime.now()
            
            # If file is from today and it's after trading hours, or just recent enough
            # Simple logic: If today is weekday and trading, we might want fresh data.
            # If file updated today, good enough.
            if file_dt.date() == now.date():
                should_fetch = False
        except:
            pass

    if not should_fetch:
        try:
            df = pd.read_parquet(cache_path)
            if not df.empty:
                return df
        except:
            should_fetch = True
            
    # 2. Fetch from API
    if should_fetch:
        try:
            market = _get_market_code(symbol)
            # API: ak.stock_individual_fund_flow(stock="600519", market="sh")
            df = ak.stock_individual_fund_flow(stock=symbol, market=market)
            
            if df is not None and not df.empty:
                # Clean numeric columns (handle string/object types)
                for col in df.columns:
                    if col != '日期':
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Sort by date
                if '日期' in df.columns:
                    df['日期'] = pd.to_datetime(df['日期'])
                    df = df.sort_values('日期')
                
                # Save
                df.to_parquet(cache_path)
                return df
        except Exception as e:
            logger.error(f"获取历史资金流向失败 {symbol}: {e}")
            # Fallback to cache if exists (even if stale)
            if os.path.exists(cache_path):
                try:
                    return pd.read_parquet(cache_path)
                except:
                    pass
                    
    return pd.DataFrame()

def get_stock_fund_flow(symbol: str) -> dict:
    """
    获取个股资金流向数据 (Fund Flow) - Latest Snapshot.
    Wraps get_stock_fund_flow_history for backward compatibility.
    """
    try:
        # 获取完整历史
        df = get_stock_fund_flow_history(symbol)
        
        if df.empty:
            return {"error": "无数据 (History Empty)"}
        
        # Take latest row
        latest = df.iloc[-1]
        
        def safe_format(val, divisor=10000):
            """安全格式化数值"""
            try:
                if pd.isna(val):
                    return "N/A"
                return f"{float(val) / divisor:.2f}万"
            except:
                return "N/A"
        
        def safe_pct(val):
            """安全格式化百分比 (Already percent in history data?)
               Note: API returns '主力净流入-净占比' as e.g. 5.12 (meaning 5.12%) or 0.0512?
               Let's check sample output:
               Sample: '中单净流入-净占比': 8.83 -> likely 8.83%
            """
            try:
                if pd.isna(val):
                    return "N/A"
                return f"{float(val):.2f}%"
            except:
                return "N/A"
        
        # Map columns from History API to Expected Keys
        # History Cols: 日期, 收盘价, 涨跌幅, 主力净流入-净额, 主力净流入-净占比, ...
        
        price_val = latest.get("收盘价", "N/A")
        
        result = {
            "名称": symbol, # History API doesn't return Name, use symbol
            "最新价": str(price_val),
            "涨跌幅": safe_pct(latest.get("涨跌幅", 0)),
            "主力净流入": safe_format(latest.get("主力净流入-净额", 0)),
            "主力净占比": safe_pct(latest.get("主力净流入-净占比", 0)),
            "超大单净流入": safe_format(latest.get("超大单净流入-净额", 0)),
            "大单净流入": safe_format(latest.get("大单净流入-净额", 0)),
        }
        
        return result
        
    except Exception as e:
        logger.error(f"获取资金流向快照失败 {symbol}: {e}")
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

def analyze_intraday_pattern(df: pd.DataFrame) -> str:
    """
    分析分时数据，提取特征供 AI 使用。
    返回一段自然语言描述。
    """
    if df.empty:
        return "无分时数据"
        
    try:
        # 确保按时间排序
        if '时间' in df.columns:
            df = df.sort_values('时间').reset_index(drop=True)
            
        # 基础数据
        closes = df['收盘']
        volumes = df['成交量']
        
        if len(df) < 10:
            return "分时数据不足"

        # 1. 整体涨跌
        open_price = closes.iloc[0]
        close_price = closes.iloc[-1]
        total_p_change = (close_price - open_price) / open_price * 100
        
        # 2. 成交量异动 (放量判定: > 3 * 均量)
        avg_vol = volumes.mean()
        high_vol_minutes = df[df['成交量'] > 3 * avg_vol]
        high_vol_count = len(high_vol_minutes)
        
        # 3. 早盘与尾盘 (前30分钟, 后30分钟)
        first_30 = df.head(30)
        last_30 = df.tail(30)
        
        p_change_early = 0
        if not first_30.empty:
            p_change_early = (first_30['收盘'].iloc[-1] - first_30['收盘'].iloc[0]) / first_30['收盘'].iloc[0] * 100
            
        p_change_late = 0
        if not last_30.empty:
            p_change_late = (last_30['收盘'].iloc[-1] - last_30['收盘'].iloc[0]) / last_30['收盘'].iloc[0] * 100
            
        # 4. 生成描述
        summary = []
        
        # 趋势描述
        if total_p_change > 0:
            trend = "震荡上行"
        elif total_p_change < 0:
            trend = "震荡下行"
        else:
            trend = "横盘震荡"
            
        summary.append(f"全天走势{trend}（幅度 {total_p_change:.2f}%）。")
        
        # 早尾盘特征
        if abs(p_change_early) > 0.5:
            direction = "上攻" if p_change_early > 0 else "下杀"
            summary.append(f"早盘开盘后{direction}（{p_change_early:.2f}%）。")
            
        if abs(p_change_late) > 0.5:
            direction = "抢筹" if p_change_late > 0 else "跳水"
            summary.append(f"尾盘出现{direction}迹象（{p_change_late:.2f}%）。")
            
        # 量能特征
        if high_vol_count > 0:
            summary.append(f"全天出现 {high_vol_count} 次明显放量异动。")
        else:
            summary.append("全天量能平稳，无显著异动。")
            
        return "".join(summary)
        
    except Exception as e:
        logger.warning(f"分时特征分析异常: {str(e)}")
        return f"分时分析错误: {str(e)}"


def calculate_price_limits(code: str, name: str, pre_close: float) -> tuple:
    """
    根据股票代码和名称计算今日涨跌停价格。
    Return: (limit_up, limit_down)
    Rule:
    - 北交所 (8xx, 4xx, 92x): 30%
    - 科创板 (688) / 创业板 (300): 20%
    - ST股 (Name contains ST): 5%
    - 主板 (Others): 10%
    """
    if pre_close <= 0:
        return (0.0, 0.0)

    # 1. Check Rate
    rate = 0.10 # Default 10%
    
    # Priority checks
    if code.startswith(('8', '4', '92')): # BSE
        rate = 0.30
    elif code.startswith(('688', '300')): # STAR / ChiNext
        rate = 0.20
    elif 'ST' in name.upper(): # ST Stock (Main board ST is 5%, ChiNext ST is still 20%? Actually ChiNext ST is 20%)
        # Complex rule: ChiNext ST is 20%, Main ST is 5%.
        # Be simple first: If 300/688, it's 20% even if ST.
        # If Main board and ST, it's 5%.
        rate = 0.05
    
    # 2. Calculate
    # A-share rounding rule is standard rounding to 2 decimals usually.
    # Official: Round(PreClose * (1 + Rate) * 100) / 100
    
    limit_up = round(pre_close * (1 + rate), 2)
    limit_down = round(pre_close * (1 - rate), 2)
    
    return (limit_up, limit_down)


