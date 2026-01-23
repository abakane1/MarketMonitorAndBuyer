from utils.database import get_db_connection

def check_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    print("--- Intelligence Table ---")
    c.execute("SELECT symbol, data FROM intelligence LIMIT 2")
    rows = c.fetchall()
    for row in rows:
        print(f"Symbol: {row['symbol']}, Data Type: {type(row['data'])}, Data Len: {len(row['data'])}")
        # Print first 100 chars
        print(f"Content: {row['data'][:100]}...")
        
    print("\n--- Strategy Logs Table ---")
    c.execute("SELECT count(*) as count FROM strategy_logs")
    row = c.fetchone()
    print(f"Total Logs: {row['count']}")
    
    conn.close()

if __name__ == "__main__":
    check_db()
