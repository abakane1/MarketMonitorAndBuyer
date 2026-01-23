import sqlite3
import os
from datetime import datetime

DB_FILE = "user_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Positions table
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        shares INTEGER,
        cost REAL,
        base_shares INTEGER DEFAULT 0
    )''')
    
    # Allocations table
    c.execute('''CREATE TABLE IF NOT EXISTS allocations (
        symbol TEXT PRIMARY KEY,
        amount REAL
    )''')
    
    # History table
    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        type TEXT,
        price REAL,
        amount REAL,
        note TEXT
    )''')
    
    # [NEW] Watchlist table
    c.execute('''CREATE TABLE IF NOT EXISTS watchlist (
        symbol TEXT PRIMARY KEY,
        added_at TEXT
    )''')
    
    # [NEW] Intelligence table
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence (
        symbol TEXT PRIMARY KEY,
        data TEXT,
        updated_at TEXT
    )''')
    
    # [NEW] Strategy Logs table
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        result TEXT,
        reasoning TEXT,
        prompt TEXT,
        tag TEXT
    )''')
    
    # --- Schema Migration: Check if base_shares exists ---
    try:
        c.execute("SELECT base_shares FROM positions LIMIT 1")
    except sqlite3.OperationalError:
        # Column missing, add it
        print("Migrating DB: Adding base_shares column to positions table...")
        c.execute("ALTER TABLE positions ADD COLUMN base_shares INTEGER DEFAULT 0")
        conn.commit()
    
    conn.commit()
    conn.close()

# --- Positions ---

def db_get_position(symbol: str) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT shares, cost, base_shares FROM positions WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "shares": row["shares"], 
            "cost": row["cost"],
            "base_shares": row["base_shares"] if row["base_shares"] is not None else 0
        }
    return {"shares": 0, "cost": 0.0, "base_shares": 0}

def db_update_position(symbol: str, shares: int, cost: float, base_shares: int = None):
    """
    Update position. If base_shares is None, keep existing value.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if exists to preserve base_shares if not provided
    existing = None
    if base_shares is None:
        c.execute("SELECT base_shares FROM positions WHERE symbol = ?", (symbol,))
        row = c.fetchone()
        if row:
            base_shares = row["base_shares"]
        else:
            base_shares = 0
            
    c.execute("""
        INSERT OR REPLACE INTO positions (symbol, shares, cost, base_shares) 
        VALUES (?, ?, ?, ?)
    """, (symbol, shares, cost, base_shares))
        
    conn.commit()
    conn.close()

# --- Allocations ---

def db_get_allocation(symbol: str) -> float:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT amount FROM allocations WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return row["amount"]
    return 0.0

def db_set_allocation(symbol: str, amount: float):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO allocations (symbol, amount) VALUES (?, ?)", 
              (symbol, amount))
    conn.commit()
    conn.close()

# --- Watchlist ---

def db_get_watchlist() -> list:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT symbol FROM watchlist")
    rows = c.fetchall()
    conn.close()
    return [row["symbol"] for row in rows]

def db_add_watchlist(symbol: str):
    conn = get_db_connection()
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO watchlist (symbol, added_at) VALUES (?, ?)", (symbol, timestamp))
    conn.commit()
    conn.close()

def db_remove_watchlist(symbol: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()

# --- Intelligence ---

def db_save_intelligence(symbol: str, data: any):
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_data = data
    
    if isinstance(data, dict):
        target_data = data.copy()
        if "updated_at" in target_data:
            updated = target_data.pop("updated_at")
            
    import json
    json_str = json.dumps(target_data, ensure_ascii=False)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO intelligence (symbol, data, updated_at) VALUES (?, ?, ?)", 
              (symbol, json_str, updated))
    conn.commit()
    conn.close()

def db_load_intelligence(symbol: str) -> any:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT data, updated_at FROM intelligence WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    
    if row:
        import json
        try:
            data = json.loads(row["data"])
            if isinstance(data, dict):
                data["updated_at"] = row["updated_at"]
            return data
        except:
             return [] if "watchlist" not in symbol else {} # Context unaware fallback
    return [] # Default to empty list as mostly used for claims list

# --- Strategy Logs ---

def db_save_strategy_log(symbol: str, prompt: str, result: str, reasoning: str):
    conn = get_db_connection()
    c = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Try extract Tag
    import re
    tag_match = re.search(r"【(.*?)】", result)
    tag = tag_match.group(0) if tag_match else ""
    
    c.execute("""
        INSERT INTO strategy_logs (symbol, timestamp, result, reasoning, prompt, tag)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (symbol, ts, result, reasoning, prompt, tag))
    conn.commit()
    conn.close()

def db_get_strategy_logs(symbol: str, limit: int = 20) -> list:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM strategy_logs 
        WHERE symbol = ? 
        ORDER BY id DESC 
        LIMIT ?
    """, (symbol, limit))
    rows = c.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        res.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "result": r["result"],
            "reasoning": r["reasoning"],
            "prompt": r["prompt"],
            "tag": r["tag"]
        })
    return res

def db_delete_strategy_log(symbol: str, timestamp: str) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM strategy_logs WHERE symbol = ? AND timestamp = ?", (symbol, timestamp))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def db_get_latest_strategy_log(symbol: str) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM strategy_logs 
        WHERE symbol = ? 
        ORDER BY id DESC 
        LIMIT 1
    """, (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "timestamp": row["timestamp"],
            "result": row["result"],
            "reasoning": row["reasoning"],
            "prompt": row["prompt"],
            "tag": row["tag"]
        }
    return None

# --- History ---

def db_add_history(symbol: str, timestamp: str, action_type: str, price: float, amount: float, note: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO history (symbol, timestamp, type, price, amount, note) VALUES (?, ?, ?, ?, ?, ?)",
              (symbol, timestamp, action_type, price, amount, note))
    conn.commit()
    conn.close()

def db_get_history(symbol: str) -> list:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE symbol = ? ORDER BY timestamp ASC", (symbol,))
    rows = c.fetchall()
    conn.close()
    
    # Convert rows to dict list to match old API
    result = []
    for row in rows:
        result.append({
            "timestamp": row["timestamp"],
            "type": row["type"],
            "price": row["price"],
            "amount": row["amount"],
            "note": row["note"]
        })
    return result

def db_delete_transaction(symbol: str, timestamp: str) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE symbol = ? AND timestamp = ?", (symbol, timestamp))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0
