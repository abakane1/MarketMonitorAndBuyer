#!/usr/bin/env python3
"""
修复今日策略：
1. 删除基于旧数据的策略
2. 重新生成基于最新数据的策略
3. 保存到review_logs表（系统可见）
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, '/Users/zuliangzhao/MarketMonitorAndBuyer')

def get_db_connection():
    """获取数据库连接"""
    db_path = '/Users/zuliangzhao/MarketMonitorAndBuyer/user_data.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def delete_today_strategies():
    """删除今日的策略日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 删除strategy_logs中的今日记录
    cursor.execute('DELETE FROM strategy_logs WHERE date(timestamp) = ?', (today,))
    deleted_strategy = cursor.rowcount
    
    # 删除review_logs中的今日记录
    cursor.execute('DELETE FROM review_logs WHERE date(timestamp) = ?', (today,))
    deleted_review = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f'🗑️  删除今日策略记录:')
    print(f'  strategy_logs: {deleted_strategy} 条')
    print(f'  review_logs: {deleted_review} 条')
    
    return deleted_strategy + deleted_review

def run_five_step_workflow_for_symbol(symbol):
    """对单个标的运行五步工作流"""
    try:
        from scripts.five_step_moe import run_five_step_workflow
        from utils.data_fetcher import get_stock_realtime_info, get_stock_fund_flow
        from utils.config import load_config
        
        # 获取配置
        config = load_config()
        settings = config.get('settings', {})
        
        deepseek_key = settings.get('deepseek_api_key')
        qwen_key = settings.get('qwen_api_key') or settings.get('kimi_api_key')
        
        if not deepseek_key:
            print(f'❌ {symbol}: 缺少DeepSeek API密钥')
            return None
        if not qwen_key:
            print(f'❌ {symbol}: 缺少Qwen/Kimi API密钥')
            return None
        
        # 获取实时数据
        print(f'📥 {symbol}: 获取实时数据...')
        info = get_stock_realtime_info(symbol)
        if not info:
            print(f'❌ {symbol}: 无法获取实时数据')
            return None
        
        print(f'  当前价: {info.get(\"price\", \"未知\")}')
        
        # 获取持仓和历史
        from utils.database import db_get_position, db_get_history
        position = db_get_position(symbol)
        history = db_get_history(symbol)
        fund_flow = get_stock_fund_flow(symbol)
        
        print(f'  持仓: {position.get(\"shares\", 0)}股 @ 成本{position.get(\"cost\", 0):.3f}')
        
        # 运行五步工作流
        print(f'🤖 {symbol}: 运行五步工作流...')
        result = run_five_step_workflow(
            symbol=symbol,
            info=info,
            position=position,
            history=history,
            fund_flow=fund_flow,
            deepseek_api_key=deepseek_key,
            qwen_api_key=qwen_key,
            intel_hub_data=""
        )
        
        return result
        
    except Exception as e:
        print(f'❌ {symbol}: 运行失败 - {e}')
        import traceback
        traceback.print_exc()
        return None

def save_to_review_logs(symbol, result):
    """保存到review_logs表（系统可见）"""
    if not result:
        return False
    
    try:
        from utils.database import db_save_review_log
        
        final_order = result.get('final_order', '')
        reasoning = result.get('reasoning', '')
        audit_report = result.get('audit_report', '')
        
        # 构建完整的策略文本
        full_result = final_order
        if audit_report:
            full_result += f'\n\n【审计报告】\n{audit_report}'
        
        # 保存到review_logs
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db_save_review_log(
            symbol=symbol,
            prompt='五步工作流修复生成',
            result=full_result,
            reasoning=reasoning,
            model='DeepSeek',
            details='基于最新数据重新生成的策略'
        )
        
        print(f'💾 {symbol}: 策略已保存到review_logs表')
        return True
        
    except Exception as e:
        print(f'❌ {symbol}: 保存失败 - {e}')
        return False

def save_to_strategy_logs(symbol, result):
    """同时保存到strategy_logs表（备份）"""
    if not result:
        return False
    
    try:
        from utils.database import get_db_connection
        
        final_order = result.get('final_order', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO strategy_logs 
            (symbol, timestamp, result, reasoning, prompt, tag, model, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, timestamp, final_order, '', '五步工作流修复生成', '【盘前策略】', 'DeepSeek', '基于最新数据重新生成'))
        
        conn.commit()
        conn.close()
        
        print(f'💾 {symbol}: 策略已备份到strategy_logs表')
        return True
        
    except Exception as e:
        print(f'❌ {symbol}: 备份失败 - {e}')
        return False

def main():
    """主函数"""
    print('=' * 70)
    print('🔧 修复今日策略 (基于最新数据重新生成)')
    print(f'⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    symbols = ['588710', '588200', '588750', '588000', '563230']
    
    # 步骤1: 删除旧策略
    print('\n1. 🗑️ 删除基于旧数据的策略...')
    deleted = delete_today_strategies()
    print(f'   删除完成 ({deleted} 条记录)')
    
    # 步骤2: 重新生成策略
    print('\n2. 🔄 基于最新数据重新生成策略...')
    
    success_count = 0
    for symbol in symbols:
        print(f'\n📊 处理标的: {symbol}')
        print('-' * 40)
        
        # 运行五步工作流
        result = run_five_step_workflow_for_symbol(symbol)
        
        if result:
            # 保存到review_logs（系统可见）
            if save_to_review_logs(symbol, result):
                # 备份到strategy_logs
                save_to_strategy_logs(symbol, result)
                success_count += 1
        else:
            print(f'❌ {symbol}: 策略生成失败')
    
    # 步骤3: 总结
    print('\n' + '=' * 70)
    print('📊 修复完成总结')
    print(f'✅ 成功生成: {success_count}/{len(symbols)} 个标的')
    print(f'📅 策略已保存到 review_logs 表，可在系统中查看')
    print('=' * 70)
    
    # 显示新生成的策略
    if success_count > 0:
        print('\n📋 新生成策略列表:')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT symbol, timestamp, LENGTH(result) as length 
            FROM review_logs 
            WHERE date(timestamp) = ?
            ORDER BY timestamp DESC
        ''', (today,))
        
        rows = cursor.fetchall()
        for row in rows:
            print(f'  {row[0]} | {row[1][11:19]} | {row[2]}字符')
        
        conn.close()
    
    return 0 if success_count == len(symbols) else 1

if __name__ == '__main__':
    sys.exit(main())