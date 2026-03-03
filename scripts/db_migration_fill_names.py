import sqlite3
import os
import sys

# Ensure root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db_connection, init_db
from utils.data_fetcher import get_stock_name_by_code
import time

def backfill_position_names():
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT symbol, name FROM positions WHERE name = '' OR name IS NULL")
    rows = c.fetchall()
    
    if not rows:
        print("所有持仓已有名称，无需回填。")
        conn.close()
        return
        
    print(f"找到 {len(rows)} 个需要补全名称的持仓，开始回填...")
    
    updated_count = 0
    for row in rows:
        symbol = row["symbol"]
        name = get_stock_name_by_code(symbol)
        if name and name != symbol:
            c.execute("UPDATE positions SET name = ? WHERE symbol = ?", (name, symbol))
            print(f"成功补全: {symbol} -> {name}")
            updated_count += 1
        else:
            print(f"未找到名称或获取失败: {symbol}")
        time.sleep(0.1) # 略作延时以示友好且避免超频
        
    conn.commit()
    conn.close()
    
    print(f"回填完成，共更新 {updated_count} 条记录。")

if __name__ == '__main__':
    backfill_position_names()
