#!/usr/bin/env python3
"""
将今日收盘后生成的策略从strategy_logs迁移到review_logs表
确保系统能够显示最新策略
"""
import sys
import sqlite3
from datetime import datetime

def get_db_connection():
    """获取数据库连接"""
    db_path = '/Users/zuliangzhao/MarketMonitorAndBuyer/user_data.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_today_strategies():
    """迁移今日策略"""
    print('=' * 70)
    print('🔄 迁移今日策略到review_logs表')
    print(f'⏰ 时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 步骤1: 删除review_logs表中今天的记录
    print('\n1. 🗑️ 清理review_logs表今日记录...')
    cursor.execute('DELETE FROM review_logs WHERE date(timestamp) = ?', (today,))
    deleted_review = cursor.rowcount
    print(f'   删除 {deleted_review} 条记录')
    
    # 步骤2: 获取strategy_logs表中今天收盘后的策略
    print('\n2. 📥 获取收盘后生成的策略...')
    cursor.execute('''
        SELECT symbol, timestamp, result, tag, model, details 
        FROM strategy_logs 
        WHERE date(timestamp) = ? 
          AND tag = '【盘前策略】'
          AND time(timestamp) >= '15:00:00'
        ORDER BY timestamp DESC
    ''', (today,))
    
    strategies = cursor.fetchall()
    print(f'   找到 {len(strategies)} 条收盘后策略')
    
    # 步骤3: 插入到review_logs表
    print('\n3. 💾 迁移到review_logs表...')
    migrated_count = 0
    
    for strategy in strategies:
        symbol = strategy['symbol']
        timestamp = strategy['timestamp']
        result = strategy['result']
        tag = strategy['tag']
        model = strategy['model'] or 'DeepSeek'
        details = strategy['details'] or ''
        
        # 构建prompt和reasoning
        prompt = f"批量策略生成器 - {tag}"
        
        # 从result中提取reasoning（如果有的话）
        reasoning = ''
        if '推理过程' in result or '思考过程' in result:
            # 尝试提取推理部分
            lines = result.split('\n')
            reasoning_lines = []
            in_reasoning = False
            for line in lines:
                if '推理过程' in line or '思考过程' in line:
                    in_reasoning = True
                    continue
                if in_reasoning and ('【' in line or '---' in line or line.strip() == ''):
                    in_reasoning = False
                    continue
                if in_reasoning:
                    reasoning_lines.append(line)
            reasoning = '\n'.join(reasoning_lines)
        
        # 插入到review_logs
        cursor.execute('''
            INSERT INTO review_logs 
            (symbol, timestamp, result, reasoning, prompt, tag, model, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, timestamp, result, reasoning, prompt, tag, model, details))
        
        migrated_count += 1
        print(f'   ✅ {symbol} | {timestamp[11:19]} | {model}')
    
    # 步骤4: 提交并验证
    conn.commit()
    
    # 验证迁移结果
    print('\n4. 🔍 验证迁移结果...')
    cursor.execute('SELECT COUNT(*) FROM review_logs WHERE date(timestamp) = ?', (today,))
    review_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f'   review_logs表今日记录数: {review_count}')
    
    # 显示迁移结果
    print('\n' + '=' * 70)
    print('📊 迁移完成总结')
    print(f'✅ 成功迁移: {migrated_count} 条策略到review_logs表')
    print(f'📅 现在系统应该能够显示今日策略')
    print('=' * 70)
    
    # 显示新迁移的策略列表
    if migrated_count > 0:
        print('\n📋 已迁移策略列表:')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, timestamp, model 
            FROM review_logs 
            WHERE date(timestamp) = ?
            ORDER BY timestamp DESC
        ''', (today,))
        
        rows = cursor.fetchall()
        for row in rows:
            print(f'  {row["symbol"]} | {row["timestamp"][11:19]} | {row["model"]}')
        
        conn.close()
    
    return migrated_count

def main():
    """主函数"""
    try:
        migrated = migrate_today_strategies()
        return 0 if migrated > 0 else 1
    except Exception as e:
        print(f'❌ 迁移失败: {e}')
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())