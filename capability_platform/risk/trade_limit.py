# -*- coding: utf-8 -*-
"""
交易限制检查 - 简化版（无24小时限制）

可选的风控逻辑，可以禁用。
"""

import sqlite3
from datetime import datetime
from typing import Tuple


# 全局开关
ENABLE_TRADE_LIMIT = False  # 默认关闭交易限制
MAX_DAILY_TRADES = 3       # 每日交易上限（仅在开启限制时使用）


def set_trade_limit_enabled(enabled: bool):
    """设置是否启用交易限制"""
    global ENABLE_TRADE_LIMIT
    ENABLE_TRADE_LIMIT = enabled


def check_trade_limit(symbol: str, action: str, db_path: str = "user_data.db") -> Tuple[bool, str]:
    """
    检查交易限制（简化版）
    
    当前配置：
    - 交易限制默认关闭
    - 如需开启，调用 set_trade_limit_enabled(True)
    
    Args:
        symbol: 股票代码
        action: 交易动作
        db_path: 数据库路径
        
    Returns:
        (是否允许, 消息)
    """
    # 如果限制未开启，直接通过
    if not ENABLE_TRADE_LIMIT:
        return True, "交易限制已关闭"
    
    # 只有买入卖出才需要检查
    action_str = str(action).lower()
    if action_str not in ['buy', 'sell', '买入', '卖出', '快速交易']:
        return True, "非交易操作，跳过检查"
    
    # 检查每日次数
    return check_daily_trade_count(db_path)


def check_daily_trade_count(db_path: str = "user_data.db") -> Tuple[bool, str]:
    """
    检查每日交易次数
    
    Returns:
        (是否允许, 消息)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT COUNT(*) FROM history 
        WHERE date(timestamp) = ? 
        AND type IN ('buy', 'sell', '买入', '卖出', '快速交易')
    """, (today,))
    today_count = cursor.fetchone()[0]
    conn.close()
    
    if today_count >= MAX_DAILY_TRADES:
        return False, f"今日交易次数已达上限({MAX_DAILY_TRADES}次)，已交易{today_count}次"
    
    return True, f"通过检查 (今日已交易{today_count}/{MAX_DAILY_TRADES}次)"


def get_today_trade_count(db_path: str = "user_data.db") -> int:
    """获取今日交易次数"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT COUNT(*) FROM history 
        WHERE date(timestamp) = ? 
        AND type IN ('buy', 'sell', '买入', '卖出', '快速交易')
    """, (today,))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count
