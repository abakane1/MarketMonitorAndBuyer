import sqlite3
import os
from datetime import datetime
import streamlit as st

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
    
    # [LAB] Strategy Logs table (For Lab/Backtest)
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        result TEXT,
        reasoning TEXT,
        prompt TEXT,
        tag TEXT,
        model TEXT DEFAULT 'DeepSeek'
    )''')
    
    # [PROD] Review Logs table (For Strategy Section)
    c.execute('''CREATE TABLE IF NOT EXISTS review_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp TEXT,
        result TEXT,
        reasoning TEXT,
        prompt TEXT,
        tag TEXT,
        model TEXT DEFAULT 'DeepSeek'
    )''')
    
    # --- Schema Migration: Check if base_shares exists ---
    try:
        c.execute("SELECT base_shares FROM positions LIMIT 1")
    except sqlite3.OperationalError:
        # Column missing, add it
        print("Migrating DB: Adding base_shares column to positions table...")
        c.execute("ALTER TABLE positions ADD COLUMN base_shares INTEGER DEFAULT 0")
        conn.commit()

    # --- Schema Migration: Check if model exists in strategy_logs ---
    try:
        c.execute("SELECT model FROM strategy_logs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding model column to strategy_logs table...")
        c.execute("ALTER TABLE strategy_logs ADD COLUMN model TEXT DEFAULT 'DeepSeek'")
        conn.commit()
    
    # --- Schema Migration: Check if details exists in strategy_logs ---
    try:
        c.execute("SELECT details FROM strategy_logs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding details column to strategy_logs table...")
        c.execute("ALTER TABLE strategy_logs ADD COLUMN details TEXT")
        conn.commit()
    
    # --- Schema Migration: Check if details exists in review_logs ---
    try:
        c.execute("SELECT details FROM review_logs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating DB: Adding details column to review_logs table...")
        c.execute("ALTER TABLE review_logs ADD COLUMN details TEXT")
        conn.commit()

    conn.commit()
    conn.close()

# --- Positions ---

# @st.cache_data(ttl=2) # REMOVED to prevent stale data during rapid transactions
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

@st.cache_data(ttl=5)
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

@st.cache_data(ttl=10)
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

# --- Strategy Logs (For Lab) ---

def db_save_strategy_log(symbol: str, prompt: str, result: str, reasoning: str, model: str = "DeepSeek", custom_timestamp: str = None, details: dict = None):
    conn = get_db_connection()
    c = conn.cursor()
    ts = custom_timestamp if custom_timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Try extract Tag
    import re
    tag_match = re.search(r"【(.*?)】", result)
    tag = tag_match.group(0) if tag_match else ""
    
    # Serialize details
    import json
    details_json = json.dumps(details, ensure_ascii=False) if details else None
    
    # Ensure model column exists (double check handled by Schema Migration but safe to be explicit in INSERT)
    c.execute("""
        INSERT INTO strategy_logs (symbol, timestamp, result, reasoning, prompt, tag, model, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, ts, result, reasoning, prompt, tag, model, details_json))
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
        # Compatibility with old DB rows that might have None
        mdl = r["model"] if "model" in r.keys() and r["model"] else "DeepSeek"
        res.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "result": r["result"],
            "reasoning": r["reasoning"],
            "prompt": r["prompt"],
            "tag": r["tag"],
            "model": mdl
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

def db_delete_strategy_logs_by_date(symbol: str, date_str: str) -> int:
    """
    Delete all logs for a symbol on a specific date (YYYY-MM-DD).
    """
    conn = get_db_connection()
    c = conn.cursor()
    # Match strings starting with the date
    c.execute("DELETE FROM strategy_logs WHERE symbol = ? AND timestamp LIKE ?", (symbol, f"{date_str}%"))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected

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
        mdl = row["model"] if "model" in row.keys() and row["model"] else "DeepSeek"
        return {
            "timestamp": row["timestamp"],
            "result": row["result"],
            "reasoning": row["reasoning"],
            "prompt": row["prompt"],
            "tag": row["tag"],
            "model": mdl
        }
    return None

# --- Review Logs (For Strategy Section) ---

def db_save_review_log(symbol: str, prompt: str, result: str, reasoning: str, model: str = "DeepSeek", custom_timestamp: str = None):
    conn = get_db_connection()
    c = conn.cursor()
    ts = custom_timestamp if custom_timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Try extract Tag
    import re
    tag_match = re.search(r"【(.*?)】", result)
    tag = tag_match.group(0) if tag_match else ""
    
    # Migration logic: Check if 'model' column exists in 'review_logs' table
    # This is a simple check; a more robust migration system would be preferred for complex changes.
    try:
        c.execute("SELECT model FROM review_logs LIMIT 1")
    except sqlite3.OperationalError:
        # If 'model' column does not exist, add it
        c.execute("ALTER TABLE review_logs ADD COLUMN model TEXT DEFAULT 'DeepSeek'")
        conn.commit()
    
    c.execute("""
        INSERT INTO review_logs (symbol, timestamp, result, reasoning, prompt, tag, model)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (symbol, ts, result, reasoning, prompt, tag, model))
    conn.commit()
    conn.close()

def db_get_review_logs(symbol: str, limit: int = 20) -> list:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM review_logs 
        WHERE symbol = ? 
        ORDER BY id DESC 
        LIMIT ?
    """, (symbol, limit))
    rows = c.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        mdl = r["model"] if "model" in r.keys() and r["model"] else "DeepSeek"
        res.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "result": r["result"],
            "reasoning": r["reasoning"],
            "prompt": r["prompt"],
            "tag": r["tag"],
            "model": mdl
        })
    return res

def db_delete_review_log(symbol: str, timestamp: str) -> bool:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM review_logs WHERE symbol = ? AND timestamp = ?", (symbol, timestamp))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def db_get_latest_review_log(symbol: str) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM review_logs 
        WHERE symbol = ? 
        ORDER BY id DESC 
        LIMIT 1
    """, (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        mdl = row["model"] if "model" in row.keys() and row["model"] else "DeepSeek"
        return {
            "timestamp": row["timestamp"],
            "result": row["result"],
            "reasoning": row["reasoning"],
            "prompt": row["prompt"],
            "tag": row["tag"],
            "model": mdl
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

@st.cache_data(ttl=5)
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

def db_get_position_at_date(symbol: str, target_date_str: str) -> dict:
    """Reconstructs position up to the start of a given date (00:00:00)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT type, amount, price FROM history 
        WHERE symbol = ? AND timestamp < ?
        ORDER BY timestamp ASC
    """, (symbol, target_date_str + " 00:00:00"))
    rows = c.fetchall()
    conn.close()
    
    shares = 0
    total_cost = 0.0
    for r in rows:
        t = r["type"].lower()
        qty = int(r["amount"])
        p = float(r["price"] or 0)
        
        # 处理持仓修正 (Override) - 这是解决问题的关键
        if "override" in t or "修正" in t or "reset" in t:
            shares = qty
            total_cost = qty * p
        elif any(w in t for w in ["买", "入", "buy"]):
            shares += qty
            total_cost += qty * p
        elif any(w in t for w in ["卖", "出", "sell"]):
            if shares > 0:
                # 按照移动平均减去成本
                avg_p = total_cost / shares
                shares -= qty
                if shares <= 0:
                    shares = 0
                    total_cost = 0.0
                else:
                    total_cost = shares * avg_p
            else:
                shares = 0
                total_cost = 0.0
    
    return {
        "shares": int(shares),
        "avg_cost": total_cost / shares if shares > 0 else 0.0
    }
