import os
import json
import glob
from utils.database import (
    db_add_watchlist, db_save_intelligence, db_save_strategy_log,
    db_set_allocation
)
from utils.config import load_config, save_config

def migrate_watchlist_and_allocations():
    print("--- Migrating Watchlist & Allocations ---")
    config = load_config()
    
    # 1. Watchlist
    selected = config.get("selected_stocks", [])
    for code in selected:
        print(f"Adding {code} to Watchlist DB...")
        db_add_watchlist(code)
        
    # 2. Allocations
    allocs = config.get("allocations", {})
    for code, amount in allocs.items():
        print(f"Adding allocation {code}: {amount} to DB...")
        db_set_allocation(code, float(amount))

def migrate_intelligence():
    print("\n--- Migrating Intelligence ---")
    INTEL_FILE = "data/intelligence.json"
    if os.path.exists(INTEL_FILE):
        try:
            with open(INTEL_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for code, intel_data in data.items():
                    print(f"Migrating intelligence for {code}...")
                    db_save_intelligence(code, intel_data)
        except Exception as e:
            print(f"Error reading intelligence.json: {e}")
    else:
        print("No intelligence.json found.")

def migrate_strategy_logs():
    print("\n--- Migrating Strategy Logs ---")
    LOG_DIR = "logs"
    if not os.path.exists(LOG_DIR):
        print("No logs directory found.")
        return

    json_files = glob.glob(os.path.join(LOG_DIR, "strategy_analysis_*.json"))
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                log_data = json.load(f)
                # Filename usually has code? strategy_analysis_600076.json
                # Actually previously app appended to list in a single file per stock?
                # Let's check format. It seems the file IS the log for one stock?
                # Or a list of logs?
                # Assuming list of logs as per storage.py logic (load_research_log returns list)
                
                # Extract code from filename
                filename = os.path.basename(file_path)
                code = filename.replace("strategy_analysis_", "").replace(".json", "")
                
                if isinstance(log_data, list):
                    for entry in log_data:
                        prompt = entry.get('prompt', '')
                        result = entry.get('result', '')
                        reasoning = entry.get('reasoning', '')
                        # Timestamp might be in entry?
                        # user config: 'timestamp' key
                        # db expects: symbol, prompt, result, reasoning
                        # But db_save sets its current timestamp?
                        # We should INSERT directly to preserve timestamp.
                        
                        # Direct DB Insert to preserve timestamp
                        from utils.database import get_db_connection
                        conn = get_db_connection()
                        c = conn.cursor()
                        ts = entry.get('timestamp', '')
                        
                        import re
                        tag_match = re.search(r"【(.*?)】", result)
                        tag = tag_match.group(0) if tag_match else ""
                        
                        c.execute("""
                            INSERT INTO strategy_logs (symbol, timestamp, result, reasoning, prompt, tag)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (code, ts, result, reasoning, prompt, tag))
                        conn.commit()
                        conn.close()
                        
                    print(f"Migrated {len(log_data)} logs for {code}")
        except Exception as e:
            print(f"Error migrating {file_path}: {e}")

if __name__ == "__main__":
    migrate_watchlist_and_allocations()
    migrate_intelligence()
    migrate_strategy_logs()
    print("\nMigration Complete.")
