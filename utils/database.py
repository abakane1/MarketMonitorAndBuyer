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
        cost REAL
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
    
    conn.commit()
    conn.close()

# --- Positions ---

def db_get_position(symbol: str) -> dict:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT shares, cost FROM positions WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"shares": row["shares"], "cost": row["cost"]}
    return {"shares": 0, "cost": 0.0}

def db_update_position(symbol: str, shares: int, cost: float):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO positions (symbol, shares, cost) VALUES (?, ?, ?)", 
              (symbol, shares, cost))
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
