# -*- coding: utf-8 -*-
"""
Data Source Fallback Module

Provides fallback data sources when akshare/EastMoney is blocked.
"""

import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Sina Finance API (often more reliable)
def get_stock_spot_sina(symbol: str) -> Optional[Dict]:
    """
    Fetch real-time stock data from Sina Finance API.
    
    Args:
        symbol: Stock code like 'sh600076' or 'sz300059'
    
    Returns:
        Dict with stock data or None if failed
    """
    try:
        # 转换代码前缀：6/5 开头 → 上交所(sh)，0/3 开头 → 深交所(sz)
        if symbol.startswith(('6', '5')):
            sina_symbol = f"sh{symbol}"
        elif symbol.startswith(('0', '3')):
            sina_symbol = f"sz{symbol}"
        else:
            sina_symbol = symbol
        
        url = f"https://hq.sinajs.cn/list={sina_symbol}"
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gb2312'
        
        # Parse Sina response format
        # var hq_str_sh600076="东方通信,12.50,12.40,12.55,12.60,12.45,12.55,12.56,12345,15432000,...
        data_str = response.text
        if not data_str or '=""' in data_str:
            return None
        
        # Extract data between quotes
        start = data_str.find('"') + 1
        end = data_str.rfind('"')
        if start <= 0 or end <= start:
            return None
        
        fields = data_str[start:end].split(',')
        if len(fields) < 33:
            return None
        
        # Sina field mapping
        # 0: name, 1: open, 2: close(yesterday), 3: current, 4: high, 5: low
        # 8: volume, 9: amount
        return {
            '代码': symbol,
            '名称': fields[0],
            '最新价': float(fields[3]),
            '今开': float(fields[1]),
            '昨收': float(fields[2]),
            '最高': float(fields[4]),
            '最低': float(fields[5]),
            '成交量': float(fields[8]),
            '成交额': float(fields[9]),
            '涨跌幅': (float(fields[3]) - float(fields[2])) / float(fields[2]) * 100 if float(fields[2]) > 0 else 0,
            '来源': 'sina'
        }
    except Exception as e:
        logger.warning(f"Sina API failed for {symbol}: {e}")
        return None


def get_stock_spot_tencent(symbol: str) -> Optional[Dict]:
    """
    Fetch real-time stock data from Tencent Finance API.
    
    Args:
        symbol: Stock code like 'sh600076'
    
    Returns:
        Dict with stock data or None if failed
    """
    try:
        # 转换代码前缀：6/5 开头 → 上交所(sh)，0/3 开头 → 深交所(sz)
        if symbol.startswith(('6', '5')):
            tencent_symbol = f"sh{symbol}"
        elif symbol.startswith(('0', '3')):
            tencent_symbol = f"sz{symbol}"
        else:
            tencent_symbol = symbol
        
        url = f"https://qt.gtimg.cn/q={tencent_symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gb2312'
        
        # Parse Tencent response format
        # v_sh600076="1~东方通信~600076~12.55~12.40~12.50~12345~...
        data_str = response.text
        if not data_str or 'v_' not in data_str:
            return None
        
        start = data_str.find('"') + 1
        end = data_str.rfind('"')
        if start <= 0 or end <= start:
            return None
        
        fields = data_str[start:end].split('~')
        if len(fields) < 45:
            return None
        
        # Tencent field mapping
        # 1: name, 2: code, 3: current, 4: close(yesterday), 5: open
        # 6: volume, 33: high, 34: low
        return {
            '代码': symbol,
            '名称': fields[1],
            '最新价': float(fields[3]),
            '今开': float(fields[5]),
            '昨收': float(fields[4]),
            '最高': float(fields[33]),
            '最低': float(fields[34]),
            '成交量': float(fields[6]),
            '成交额': 0,  # Not directly available
            '涨跌幅': (float(fields[3]) - float(fields[4])) / float(fields[4]) * 100 if float(fields[4]) > 0 else 0,
            '来源': 'tencent'
        }
    except Exception as e:
        logger.warning(f"Tencent API failed for {symbol}: {e}")
        return None


def get_stock_spot_with_fallback(symbol: str) -> Optional[Dict]:
    """
    Try multiple data sources to get stock spot data.
    
    Priority:
    1. Local cache (if fresh)
    2. Sina API
    3. Tencent API
    4. Local cache (stale)
    
    Args:
        symbol: Stock code like '600076'
    
    Returns:
        Dict with stock data or None if all sources failed
    """
    # Try to load from local cache first (if available)
    try:
        from utils.storage import load_realtime_quote, SPOT_DATA_PATH
        local_data = load_realtime_quote(symbol)
        if local_data and os.path.exists(SPOT_DATA_PATH):
            mtime = os.path.getmtime(SPOT_DATA_PATH)
            age_hours = (time.time() - mtime) / 3600
            if age_hours < 1:
                logger.info(f"Using fresh local cache for {symbol}")
                return local_data
    except ImportError:
        local_data = None
    
    # Try Sina API
    sina_data = get_stock_spot_sina(symbol)
    if sina_data:
        logger.info(f"Using Sina API for {symbol}")
        return sina_data
    
    # Try Tencent API
    tencent_data = get_stock_spot_tencent(symbol)
    if tencent_data:
        logger.info(f"Using Tencent API for {symbol}")
        return tencent_data
    
    # Fall back to local cache even if stale
    if local_data:
        logger.warning(f"Using stale local cache for {symbol}")
        return local_data
    
    logger.error(f"All data sources failed for {symbol}")
    return None


def test_data_sources():
    """Test all available data sources"""
    test_symbols = ['600076', '588200', '300059']
    
    print("Testing data sources...\n")
    
    for symbol in test_symbols:
        print(f"Testing {symbol}:")
        
        # Test Sina
        sina = get_stock_spot_sina(symbol)
        print(f"  Sina: {'✅' if sina else '❌'} {sina.get('最新价') if sina else 'N/A'}")
        
        # Test Tencent
        tencent = get_stock_spot_tencent(symbol)
        print(f"  Tencent: {'✅' if tencent else '❌'} {tencent.get('最新价') if tencent else 'N/A'}")
        
        # Test fallback
        fallback = get_stock_spot_with_fallback(symbol)
        print(f"  Fallback: {'✅' if fallback else '❌'} {fallback.get('最新价') if fallback else 'N/A'}")
        print()


if __name__ == "__main__":
    test_data_sources()
