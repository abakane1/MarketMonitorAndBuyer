from utils.database import get_db_connection

def check_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM positions")
    rows = c.fetchall()
    print("Positions in DB:")
    for row in rows:
        print(dict(row))
    conn.close()

if __name__ == "__main__":
    check_db()
