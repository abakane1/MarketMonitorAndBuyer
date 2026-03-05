#!/usr/bin/env python3
"""
发送每日盘前策略到飞书群
用法: 
  python3 send_daily_strategy.py [--dry-run] [--test]
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime
import sqlite3

# 添加路径
sys.path.insert(0, '/Users/zuliangzhao/MarketMonitorAndBuyer')

def get_db_connection():
    """获取数据库连接"""
    db_path = '/Users/zuliangzhao/MarketMonitorAndBuyer/user_data.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_today_strategies():
    """获取今日策略"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT symbol, timestamp, result 
        FROM strategy_logs 
        WHERE date(timestamp) = ? AND tag = '【盘前策略】'
        ORDER BY timestamp DESC
    ''', (today,))
    
    rows = cursor.fetchall()
    conn.close()
    
    strategies = []
    for row in rows:
        strategies.append({
            'symbol': row['symbol'],
            'time': row['timestamp'][11:19],
            'result': row['result']
        })
    
    return strategies

def format_strategy_message(strategies):
    """格式化策略消息"""
    if not strategies:
        return "📭 今日尚无盘前策略，请先运行策略生成脚本。"
    
    today = datetime.now().strftime('%Y-%m-%d')
    message = f"📊 {today} 盘前策略汇总\\n\\n"
    
    for s in strategies:
        symbol = s['symbol']
        time = s['time']
        result = s['result']
        
        # 提取关键指令
        lines = result.split('\n')
        key_lines = []
        
        # 寻找关键行
        for line in lines:
            line = line.strip()
            if (line.startswith('-') or line.startswith('[') or 
                '指令' in line or '方向' in line or '价格' in line or 
                '股' in line and len(line) > 5):
                key_lines.append(line)
        
        # 取前3条关键指令
        if key_lines:
            instr = ' | '.join(key_lines[:3])
            if len(instr) > 80:
                instr = instr[:77] + '...'
        else:
            # 如果没有找到关键行，取前100字符
            instr = result[:100] + '...' if len(result) > 100 else result
        
        message += f"🔹 **{symbol}** ({time})\\n"
        message += f"   {instr}\\n\\n"
    
    message += "---\\n"
    message += "💡 详细策略请查看系统数据库或运行 `batch_strategy_generator.py`"
    
    return message

def send_to_feishu(message, dry_run=False):
    """发送消息到飞书群"""
    # 飞书群chat_id (当前群)
    chat_id = "oc_672bd1289d4d80d80d5fe1b3e82550f6"
    
    # 构建openclaw命令
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', f'chat:{chat_id}',
        '--message', message
    ]
    
    if dry_run:
        cmd.append('--dry-run')
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ 消息发送成功")
            print(f"输出: {result.stdout}")
            return True
        else:
            print(f"❌ 发送失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 命令执行超时")
        return False
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='发送每日盘前策略到飞书群')
    parser.add_argument('--dry-run', action='store_true', help='只测试不发送')
    parser.add_argument('--test', action='store_true', help='测试模式，发送测试消息')
    args = parser.parse_args()
    
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.test:
        print("测试模式：发送测试消息")
        message = "🔧 定时任务测试消息\\n系统定时任务配置测试成功！"
        success = send_to_feishu(message, dry_run=args.dry_run)
    else:
        print("开始发送每日策略...")
        
        # 获取策略
        strategies = get_today_strategies()
        print(f"找到 {len(strategies)} 条今日策略")
        
        if strategies:
            # 格式化消息
            message = format_strategy_message(strategies)
            print(f"消息长度: {len(message)} 字符")
            print("消息预览:")
            print("-" * 50)
            print(message[:500] + "..." if len(message) > 500 else message)
            print("-" * 50)
            
            # 发送消息
            success = send_to_feishu(message, dry_run=args.dry_run)
        else:
            print("❌ 今日无策略，发送提示消息")
            message = "📭 今日尚无盘前策略，请先运行策略生成脚本。"
            success = send_to_feishu(message, dry_run=args.dry_run)
    
    if success:
        print("🎉 操作完成")
        return 0
    else:
        print("❌ 操作失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())