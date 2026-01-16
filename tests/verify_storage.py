from utils.storage import save_minute_data, load_minute_data, get_volume_profile
import os
import shutil

# Clean up any existing test data
if os.path.exists("stock_data/300059_minute.parquet"):
    os.remove("stock_data/300059_minute.parquet")

print("--- Testing ChiNext (300059) Data Save ---")
try:
    save_minute_data("300059") # East Money
    print("Save complete.")
    
    df = load_minute_data("300059")
    print(f"Loaded {len(df)} rows.")
    if not df.empty:
        print("Columns:", df.columns.tolist())
        
    prof = get_volume_profile("300059")
    print(f"Volume Profile Generated: {len(prof)} price levels.")
    print(prof.head(3))
except Exception as e:
    print(f"Error: {e}")
