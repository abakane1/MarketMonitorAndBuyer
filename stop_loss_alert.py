#!/usr/bin/env python3
"""
风控守护系统 (v3.2.0) - 接入动态持仓与阶梯风控
循环监控当前持仓并触发止损告警。
"""

import time
import subprocess
from datetime import datetime

from utils.database import db_get_all_positions
from utils.data_fetcher import get_stock_realtime_info, is_trading_time
from utils.risk_control import get_stepped_stop_loss_price

def send_alert(message: str):
    """发送飞书提醒并打印控制台信标"""
    print(f"\n[ALERT SIGNAL] {message}\n")
    try:
        subprocess.run([
            'openclaw', 'message', 'send', 
            '--channel', 'feishu',
            '--target', 'chat:oc_35c86a6affec6e670d4288eb48bb6271',
            '--message', message
        ], timeout=10)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 提醒已发送飞书")
    except Exception as e:
        print(f"飞书推送失败, 异常跳过: {e}")

def monitor_positions():
    """核对实时持仓与阶梯止损"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 风控巡检开始...")
    positions = db_get_all_positions()
    
    if not positions:
        print("当前无活动持仓，跳过检查。")
        return
        
    alerts = []
    
    for pos in positions:
        symbol = pos["symbol"]
        shares = pos["shares"]
        cost = pos["cost"]
        name = pos.get("name", symbol)
        
        info = get_stock_realtime_info(symbol)
        if not info:
            continue
            
        current_price = info.get('最新价', 0)
        if current_price <= 0:
            continue
            
        # [风控逻辑接入] 计算基于成本的动态止损价
        # 这里尚未引入历史最高价来做完美的移动止损，仅依据实时利润做阶梯保护
        stop_price = get_stepped_stop_loss_price(cost_price=cost, current_price=current_price)
        
        profit_pct = (current_price - cost) / cost * 100
        stop_pct = (current_price - stop_price) / stop_price * 100
        
        status_msg = f"浮盈(亏) {profit_pct:+.2f}% | 距离风控线 {stop_pct:+.2f}%"
        
        if current_price <= stop_price:
            status_msg = f"🚨 击穿风控底线!"
            alerts.append(f"⛔ **【风控拦截】{name} ({symbol})**\n   成本: ￥{cost:.3f} | 现价: ￥{current_price:.3f}\n   风控线: ￥{stop_price:.3f}\n   持仓: {shares:,}股")
            
        print(f" > {name}({symbol}): 现价￥{current_price:.3f} / 风控线￥{stop_price:.3f} | {status_msg}")
        
    if alerts:
        message = "⚠️ **实时风控告警**\n\n" + "\n\n".join(alerts)
        send_alert(message)
    else:
        print("✅ 全盘风控绿灯无触发。")

def daemon_mode(interval_minutes: int = 1):
    """守护进程模式"""
    print("="*60)
    print("🛡️ A股风控守护进程已启动 (轮询间隔: 60s)")
    print("="*60)
    
    while True:
        if is_trading_time():
            monitor_positions()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 非交易时段，系统待机中...")
            
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    import sys
    # 如果参数有 --once 则只运行一次，否则长驻
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        monitor_positions()
    else:
        daemon_mode()
