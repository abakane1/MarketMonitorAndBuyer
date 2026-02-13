# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import streamlit as st
from utils.storage import load_minute_data, load_realtime_quote
from utils.indicators import calculate_indicators
from utils.data_fetcher import get_stock_fund_flow_history

def build_historical_context(code: str, target_date_str: str):
    """
    Constructs a 'mock' realtime context for a specific historical date.
    
    Args:
        code: Stock code
        target_date_str: "YYYY-MM-DD"
        
    Returns:
        dict: Context dictionary compatible with strategy generation prompts.
              Returns None if insufficient data.
    """
    
    # 1. Load Minute Data
    df = load_minute_data(code)
    if df.empty:
        return None
        
    # Ensure datetime
    if '时间' in df.columns:
        df['时间'] = pd.to_datetime(df['时间'])
        
    target_date = pd.to_datetime(target_date_str)
    
    # Filter data UP TO target_date 15:00:00 (End of trading day)
    # We assume 'target_date' implies we are doing "Post-market Review" for that day.
    # So we include all data of that day.
    
    cutoff_time = target_date + pd.Timedelta(hours=15, minutes=30)
    
    historical_df = df[df['时间'] <= cutoff_time].copy()
    
    if historical_df.empty:
        return None
        
    # Check if we actually have data FOR target_date
    # (Maybe data stops before target date)
    last_row_date = historical_df.iloc[-1]['时间'].date()
    if str(last_row_date) != target_date_str:
        # Warning: No data for the exact target date?
        # Maybe it was a non-trading day?
        # We'll return what we have but warn?
        # For strict backtest, we should probably return None or warn.
        # But let's proceed with whatever 'latest' state was at that time.
        pass

    # 2. Resample to Daily for Indicators (Up to target date)
    # We need a daily series to calculate MA/MACD correctly.
    # Method: Resample minute data to Daily.
    
    daily_df = _resample_to_daily(historical_df)
    
    # 3. Calculate Indicators
    indicators = calculate_indicators(daily_df)
    
    # 4. Get Price Info (Snapshot at cutoff)
    last_row = historical_df.iloc[-1]
    price = float(last_row['收盘'])
    
    # Find Pre-Close (Close of Previous Trading Day)
    # daily_df should be sorted
    if len(daily_df) >= 2:
        pre_close = float(daily_df.iloc[-2]['收盘'])
    else:
        pre_close = price # Fallback
        
    change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0
    
    # 5. Get Fund Flow (History)
    ff_str = "无资金流数据"
    try:
        ff_hist = get_stock_fund_flow_history(code, force_update=False)
        if not ff_hist.empty:
            # Find row for target_date
            # ff_hist['日期'] is usually Timestmap or string?
            # data_fetcher usually returns DataFrame with '日期' column.
            # Let's ensure format. 
            # If '日期' is string YYYY-MM-DD
            mask = ff_hist['日期'].astype(str) == target_date_str
            ff_row = ff_hist[mask]
            
            if not ff_row.empty:
                row = ff_row.iloc[0]
                # Format: "主力净流入: -4119.39万 (-8.64%) | 超大单: -2366.69万"
                main_net = row.get('主力净流入-净额', 0) / 10000 # 万
                main_pct = row.get('主力净流入-净占比', 0)
                super_net = row.get('超大单净流入-净额', 0) / 10000
                
                ff_str = f"主力净流入: {main_net:.2f}万 ({main_pct:.2f}%) | 超大单: {super_net:.2f}万"
            else:
                ff_str = "当日无资金流记录"
    except Exception:
        ff_str = "资金流获取失败"

    # 6. Intraday Summary (Mock from Price Action)
    # Simple heuristic
    open_p = float(last_row.get('开盘', daily_df.iloc[-1]['开盘']))
    high_p = float(daily_df.iloc[-1]['最高'])
    low_p = float(daily_df.iloc[-1]['最低'])
    
    intra_summary = f"开盘: {open_p:.2f}, 最高: {high_p:.2f}, 最低: {low_p:.2f}, 收盘: {price:.2f}."
    if price > open_p:
        intra_summary += " 日内走势: 震荡上行 (Mock)"
    else:
        intra_summary += " 日内走势: 震荡下行 (Mock)"

    # 7. Construct Result
    context = {
        'code': code,
        'name': 'Unknown', # Lab should pass name or we fetch from DB
        'price': price,
        'pre_close': pre_close,
        'open': open_p,
        'high': high_p,
        'low': low_p,
        'volume': float(daily_df.iloc[-1]['成交量']),
        'amount': float(daily_df.iloc[-1]['成交额']) if '成交额' in daily_df.columns else 0,
        'date': target_date_str,
        'market_status': 'CLOSED', # Backtest is always closed-view usually
        
        # Indicator Strings
        'ma_info': indicators.get('MA', 'N/A'),
        'macd_info': indicators.get('MACD', 'N/A'),
        'kdj_info': indicators.get('KDJ', 'N/A'),
        'rsi_info': f"RSI: {indicators.get('RSI(14)', 'N/A')}",
        'boll_info': indicators.get('Bollinger', 'N/A'),
        'signal_summary': indicators.get('signal_summary', 'N/A'),
        
        # Flow
        'capital_flow_str': ff_str,
        
        # Text
        'intraday_summary': intra_summary,
        'limit_up': round(pre_close * 1.10, 2), # Approx
        'limit_down': round(pre_close * 0.90, 2),
        
        # Research Context (Empty for now, or fetch historical news if available)
        'research_context': f"【历史回溯模式】\n基准日期: {target_date_str}\n(注: 新闻面数据暂缺，仅基于量化数据分析)",
        
        # Raw Data for Red Team
        'raw_context': f"日期: {target_date_str}\n价格: {price}\n涨跌: {change_pct:.2f}%\n{ff_str}\n{indicators.get('signal_summary', '')}"
    }
    
    return context

def _resample_to_daily(minute_df):
    """
    Aggregates minute data (DataFrame) to Daily OHLCV.
    """
    # Assuming '时间' is datetime and sorted
    # We group by Date
    
    minute_df['Date'] = minute_df['时间'].dt.date
    
    agg_rules = {
        '开盘': 'first',
        '最高': 'max',
        '最低': 'min',
        '收盘': 'last',
        '成交量': 'sum',
        '时间': 'last' # Keep closing time
    }
    
    if '成交额' in minute_df.columns:
        agg_rules['成交额'] = 'sum'
        
    daily_df = minute_df.groupby('Date').agg(agg_rules).reset_index(drop=True)
    
    # Sort
    daily_df = daily_df.sort_values('时间')
    
    return daily_df
