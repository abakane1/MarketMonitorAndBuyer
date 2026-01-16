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
    df['price_bin'] = df['收盘'].round(4)
    
    profile = df.groupby('price_bin')['成交量'].sum().reset_index()
    profile = profile.sort_values('price_bin')
    return profile, meta
