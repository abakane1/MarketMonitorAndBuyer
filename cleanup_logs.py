from utils.database import get_db_connection

def clean_logs():
    symbol = "588200"
    conn = get_db_connection()
    c = conn.cursor()
    
    # Delete logs with tags indicating simulation/backtest
    query = "DELETE FROM strategy_logs WHERE symbol = ? AND (tag LIKE '%回补%' OR tag LIKE '%Backtest%' OR tag LIKE '%Simulated%')"
    c.execute(query, (symbol,))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    print(f"Deleted {deleted} simulation logs for {symbol}")

if __name__ == "__main__":
    clean_logs()
