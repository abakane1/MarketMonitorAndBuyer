
import json
import os

CONFIG_FILE = "user_config.json"

def cleanup():
    if not os.path.exists(CONFIG_FILE):
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    keys_to_remove = ["positions", "allocations", "history"]
    removed = []
    
    for key in keys_to_remove:
        if key in data:
            del data[key]
            removed.append(key)
            
    if removed:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Removed keys from {CONFIG_FILE}: {removed}")
    else:
        print("No keys to remove.")

if __name__ == "__main__":
    cleanup()
