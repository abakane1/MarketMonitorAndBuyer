import pandas as pd
import os
from datetime import datetime

import streamlit as st

DATA_DIR = "stock_data"

def init_storage():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path(symbol: str, type: str) -> str:
    """Type: 'daily' or 'minute'"""
    return os.path.join(DATA_DIR, f"{symbol}_{type}.parquet")

SPOT_DATA_PATH = os.path.join(DATA_DIR, "realtime_quotes.parquet")

def save_realtime_data(df: pd.DataFrame):
    """
    Saves the full market snapshot to disk.
    """
    init_storage()
    if not df.empty:
        df.to_parquet(SPOT_DATA_PATH)

def load_realtime_quote(symbol: str) -> dict:
    """
    Reads latest quote for a symbol from local disk.
    Returns dict or None.
    """
    if not os.path.exists(SPOT_DATA_PATH):
        return None
        
    try:
        # Optim: We could cache the whole DF in memory (st.cache_resource) but for now read is fast enough for UI?
        # Maybe use st.cache_data?
        # But if we want instant manual refresh updates, cache needs to be invalidated.
        # Let's read file directly for "One Source of Truth". Parquet is fast.
        df = pd.read_parquet(SPOT_DATA_PATH)
        
        row = df[df['代码'] == symbol]
        if row.empty:
            return None
            
        return row.iloc[0].to_dict()
    except Exception:
        return None

def save_minute_data(symbol: str):
    """
    Fetches latest minute data and merges with local history.
    """
    init_storage()
    file_path = get_file_path(symbol, 'minute')
    
    # 1. Fetch new data (usually last 5 days from API)
    from utils.data_fetcher import get_stock_minute_data
    new_df = get_stock_minute_data(symbol)
    if new_df.empty:
        return
    
    # Ensure datetime format
    new_df['时间'] = pd.to_datetime(new_df['时间'])
    
    # 2. Load existing
    if os.path.exists(file_path):
        try:
            existing_df = pd.read_parquet(file_path)
            # Merge
            combined = pd.concat([existing_df, new_df])
            # Drop duplicates based on Time, keep last
            combined = combined.drop_duplicates(subset=['时间'], keep='last')
            combined = combined.sort_values('时间')
            combined.to_parquet(file_path)
        except Exception as e:
            print(f"Error reading/saving {file_path}: {e}")
            # If error, maybe just overwrite? Safe to backup? for now overwrite
            new_df.to_parquet(file_path)
    else:
        new_df.to_parquet(file_path)

# @st.cache_data(ttl=60)
def load_minute_data(symbol: str) -> pd.DataFrame:
    file_path = get_file_path(symbol, 'minute')
    if os.path.exists(file_path):
        return pd.read_parquet(file_path)
    return pd.DataFrame()

def has_minute_data(symbol: str) -> bool:
    """
    Checks if minute data exists locally.
    """
    file_path = get_file_path(symbol, 'minute')
    return os.path.exists(file_path)

@st.cache_data(ttl=60)
def get_volume_profile(symbol: str):
    """
    Calculates Volume by Price from local minute data.
    Returns (DataFrame, MetaDataDict)
    """
    df = load_minute_data(symbol)
    if df.empty:
        return pd.DataFrame(), {}
    
    # Metadata
    meta = {
        "start_date": df['时间'].iloc[0],
        "end_date": df['时间'].iloc[-1],
        "count": len(df)
    }

    # Groups
    from utils.data_fetcher import get_price_precision
    precision = get_price_precision(symbol)
    
    df['price_bin'] = df['收盘'].round(precision)
    
    profile = df.groupby('price_bin')['成交量'].sum().reset_index()
    profile = profile.sort_values('price_bin')
    
    return profile, meta

from utils.database import (
    db_save_strategy_log, db_get_strategy_logs, 
    db_delete_strategy_log, db_get_latest_strategy_log,
    db_save_review_log, db_get_review_logs,
    db_delete_review_log, db_get_latest_review_log
)

def save_research_log(symbol: str, prompt: str, result: str, reasoning: str):
    """
    Saves a research record to LAB strategy_logs (Experimental).
    """
    db_save_strategy_log(symbol, prompt, result, reasoning)

def load_research_log(symbol: str) -> list:
    """
    Loads past research records from LAB strategy_logs.
    """
    return db_get_strategy_logs(symbol, limit=50)

def delete_research_log(symbol: str, timestamp: str) -> bool:
    return db_delete_strategy_log(symbol, timestamp)

def get_latest_strategy_log(symbol: str):
    return db_get_latest_strategy_log(symbol)

# --- Production Logs (Review & Prediction) ---

def save_production_log(symbol: str, prompt: str, result: str, reasoning: str, model: str = "DeepSeek"):
    """
    Saves a finalized strategy to review_logs (Production).
    """
    db_save_review_log(symbol, prompt, result, reasoning, model)

def load_production_log(symbol: str) -> list:
    """
    Loads confirmed strategies from review_logs (Production).
    """
    return db_get_review_logs(symbol, limit=50)

def delete_production_log(symbol: str, timestamp: str) -> bool:
    return db_delete_review_log(symbol, timestamp)

def get_latest_production_log(symbol: str):
    return db_get_latest_review_log(symbol)

def get_strategy_storage_path(symbol: str) -> str:
    return os.path.join(DATA_DIR, f"{symbol}_strategies.json")

def save_daily_strategy(symbol: str, target_date: str, advice: str, reasoning: str, prompt: str = ""):
    """
    Saves the strategy for a specific backtest target date.
    Keyed by symbol + date. Overwrites if exists.
    
    Args:
        symbol: 股票代码
        target_date: 目标日期
        advice: AI 决策输出
        reasoning: AI 思考过程
        prompt: 发送给 AI 的提示词
    """
    init_storage()
    file_path = get_strategy_storage_path(symbol)
    
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}
            
    # Update or Add
    data[target_date] = {
        "advice": advice,
        "reasoning": reasoning,
        "prompt": prompt,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_daily_strategy(symbol: str, target_date: str) -> dict:
    """
    Loads strategy for a specific date. Returns None if not found.
    """
    file_path = get_strategy_storage_path(symbol)
    if not os.path.exists(file_path):
        return None
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(target_date)
    except:
        return None
