import sqlite3
import json
import uuid
from datetime import datetime
import os
import sys

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.database import get_db_connection

def migrate():
    conn = get_db_connection()
    c = conn.cursor()
    
    print("开始迁移 intelligence 数据至 intelligence_v2...")
    
    # 确保新表存在
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence_v2 (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        source TEXT,
        timestamp TEXT,
        status TEXT DEFAULT 'pending',
        note TEXT,
        distinct_from TEXT,
        is_archived INTEGER DEFAULT 0,
        summary TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence_stocks (
        intel_id TEXT,
        symbol TEXT,
        confidence REAL,
        PRIMARY KEY (intel_id, symbol)
    )''')
    
    # 读取旧数据
    try:
        c.execute("SELECT symbol, data, updated_at FROM intelligence")
        rows = c.fetchall()
    except sqlite3.OperationalError as e:
        print(f"读取旧表失败: {e}，可能表不存在或结构已变。")
        conn.close()
        return

    migrated_count = 0
    total_symbols = len(rows)
    print(f"共发现 {total_symbols} 个 symbols。")
    
    for row in rows:
        symbol = row['symbol']
        data_str = row['data']
        # print(f"Processing symbol: {symbol}")
        
        try:
            claims = json.loads(data_str)
            if not isinstance(claims, list):
                if isinstance(claims, dict) and "watchlist" in symbol:
                    continue # Ignore watchlist format
                continue
                
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                    
                intel_id = claim.get('id', str(uuid.uuid4())[:8])
                content = claim.get('content', '')
                source = claim.get('source', '')
                timestamp = claim.get('timestamp', '')
                status = claim.get('status', 'pending')
                note = claim.get('note', '')
                
                distinct_from_list = claim.get('distinct_from', [])
                distinct_from = json.dumps(distinct_from_list) if distinct_from_list else "[]"
                
                # 插入 v2 表 (使用 INSERT OR IGNORE 避免重复，或 REPLACE 以更新)
                c.execute("""
                    INSERT OR REPLACE INTO intelligence_v2 
                    (id, content, source, timestamp, status, note, distinct_from, is_archived, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, '')
                """, (intel_id, content, source, timestamp, status, note, distinct_from))
                
                # 插入关联表 (Confidence 默认为 1.0 表示手工确切关联)
                try:
                    c.execute("""
                        INSERT OR REPLACE INTO intelligence_stocks
                        (intel_id, symbol, confidence)
                        VALUES (?, ?, 1.0)
                    """, (intel_id, symbol))
                    migrated_count += 1
                except sqlite3.Error as e:
                    print(f"Error inserting into intelligence_stocks: {e}")
                
        except json.JSONDecodeError:
            print(f"解析 symbol {symbol} 的 JSON 数据失败。跳过。")
            continue
            
    conn.commit()
    conn.close()
    
    print(f"迁移完成！成功处理了 {migrated_count} 条独立情报关联记录。")

if __name__ == "__main__":
    migrate()
