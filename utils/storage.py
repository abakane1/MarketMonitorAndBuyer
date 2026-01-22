import pandas as pd
import os
from datetime import datetime
from utils.data_fetcher import get_stock_minute_data

DATA_DIR = "stock_data"

def init_storage():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path(symbol: str, type: str) -> str:
    """Type: 'daily' or 'minute'"""
    return os.path.join(DATA_DIR, f"{symbol}_{type}.parquet")

def save_minute_data(symbol: str):
    """
    Fetches latest minute data and merges with local history.
    """
    init_storage()
    file_path = get_file_path(symbol, 'minute')
    
    # 1. Fetch new data (usually last 5 days from API)
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

import json

def get_research_log_path(symbol: str) -> str:
    return os.path.join(DATA_DIR, f"{symbol}_research.json")

def save_research_log(symbol: str, prompt: str, result: str, reasoning: str):
    """
    Saves a research record (Prompt + AI Response) to a JSON log file.
    """
    init_storage()
    file_path = get_research_log_path(symbol)
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt": prompt,
        "result": result,
        "reasoning": reasoning
    }
    
    current_log = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                current_log = json.load(f)
        except:
            current_log = []
            
    current_log.append(entry)
    
    # Optional: Limit log size? Maybe keep last 50
    if len(current_log) > 50:
        current_log = current_log[-50:]
        
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(current_log, f, ensure_ascii=False, indent=2)

def load_research_log(symbol: str) -> list:
    """
    Loads past research records.
    """
    file_path = get_research_log_path(symbol)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def delete_research_log(symbol: str, timestamp: str) -> bool:
    """
    删除指定时间戳的研报记录。
    Returns True if deleted, False otherwise.
    """
    file_path = get_research_log_path(symbol)
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
        
        original_len = len(logs)
        logs = [log for log in logs if log.get("timestamp") != timestamp]
        
        if len(logs) < original_len:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            return True
        return False
    except:
        return False

def get_latest_strategy_log(symbol: str):
    """
    Returns the most recent log that is a 'New Strategy' (contains '核心任务: 独立策略构建').
    Returns None if not found or empty.
    """
    logs = load_research_log(symbol)
    if not logs:
        return None
        
    # Logs are sorted by timestamp desc (newest first)
    # FIX: load_research_log returns [old, ..., new], so we must reverse to get newest first
    for log in logs[::-1]:
        # Relaxed logic: Return the very first (newest) log we find.
        # The user likely wants to see the latest AI interaction regardless of exact prompt type.
        return log
        
        # Original strict filter (commented out for reference):
        # prompt_content = log.get("prompt", "")
        # if "核心任务: 独立策略构建" in prompt_content:
        #     return log
            
    return None

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
