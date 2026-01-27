import sqlite3
import os

DB_FILE = "user_data.db"

def clean_db():
    if not os.path.exists(DB_FILE):
        print("DB file not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    symbol = "588200"
    print(f"Deleting ALL strategy_logs for {symbol}...")
    
    c.execute("DELETE FROM strategy_logs WHERE symbol = ?", (symbol,))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    print(f"Successfully deleted {deleted} rows.")

if __name__ == "__main__":
    clean_db()
