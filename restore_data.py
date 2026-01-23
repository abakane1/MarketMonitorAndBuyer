from utils.database import db_update_position, db_get_position

def restore_data():
    # Restore 588200 Base Shares
    code = "588200"
    pos = db_get_position(code)
    print(f"Before: {pos}")
    
    # Update with base_shares = 40000
    db_update_position(code, pos['shares'], pos['cost'], base_shares=40000)
    
    pos_new = db_get_position(code)
    print(f"After: {pos_new}")

if __name__ == "__main__":
    restore_data()
