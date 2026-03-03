#!/usr/bin/env python3
"""
交易频率控制模块
- 每日最多3笔交易
- 连续交易后24小时冷静期
"""

import sqlite3
from datetime import datetime, timedelta

def check_trade_limit(symbol, action):
    """检查交易限制"""
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()
    
    # 1. 检查今日交易次数
    cursor.execute("""
        SELECT COUNT(*) FROM history 
        WHERE date(timestamp) = ? 
        AND type IN ('buy', 'sell', '买入', '卖出', '快速交易')
    """, (today,))
    today_count = cursor.fetchone()[0]
    
    if today_count >= 3:
        return False, f"今日交易次数已达上限(3次)，已交易{today_count}次"
    
    # 2. 检查该标的最近交易时间（24小时冷静期）
    cursor.execute("""
        SELECT timestamp FROM history 
        WHERE symbol = ? 
        AND type IN ('buy', 'sell', '买入', '卖出', '快速交易')
        ORDER BY timestamp DESC LIMIT 1
    """, (symbol,))
    
    row = cursor.fetchone()
    if row:
        last_trade = datetime.fromisoformat(row[0].replace(' ', 'T'))
        hours_since = (now - last_trade).total_seconds() / 3600
        
        if hours_since < 24:
            return False, f"该标的24小时内已交易，需冷静{24-hours_since:.1f}小时"
    
    conn.close()
    return True, f"通过检查 (今日已交易{today_count}/3次)"

if __name__ == "__main__":
    # 测试
    result, msg = check_trade_limit('588000', 'buy')
    print(f"[交易检查] {msg}")
