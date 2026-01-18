
import json
import os
import sys

# Add parent dir to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import init_db, db_update_position, db_set_allocation, db_add_history

CONFIG_FILE = "user_config.json"

def migrate():
    print("Starting migration...")
    
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file {CONFIG_FILE} not found. Skipping.")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    init_db()
    
    # 1. Positions
    positions = data.get("positions", {})
    print(f"Migrating {len(positions)} positions...")
    for symbol, pos in positions.items():
        db_update_position(symbol, pos.get("shares", 0), pos.get("cost", 0.0))
        print(f"  - {symbol}: {pos}")

    # 2. Allocations
    allocations = data.get("allocations", {})
    print(f"Migrating {len(allocations)} allocations...")
    for symbol, amount in allocations.items():
        db_set_allocation(symbol, float(amount))
        print(f"  - {symbol}: {amount}")

    # 3. History
    history = data.get("history", {})
    print(f"Migrating history for {len(history)} symbols...")
    count = 0
    for symbol, events in history.items():
        for e in events:
            # history in json: timestamp, type, price, amount, note
            db_add_history(
                symbol,
                e.get("timestamp"),
                e.get("type"),
                e.get("price", 0.0),
                e.get("amount", 0.0),
                e.get("note", "")
            )
            count += 1
    print(f"Migrated {count} history events.")

    print("Migration complete!")
    print("Please verify 'user_data.db' is created and populated.")

if __name__ == "__main__":
    migrate()
