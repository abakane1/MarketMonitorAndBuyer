import json
import os
from datetime import datetime
from utils.database import (
    db_get_position, db_update_position, 
    db_get_allocation, db_set_allocation,
    db_get_history, db_add_history, db_delete_transaction
)

CONFIG_FILE = "user_config.json"

DEFAULT_CONFIG = {
    # "selected_stocks": [], # DEPRECATED: Moved to DB
    # "positions": {},       # DEPRECATED: Moved to DB
    # "allocations": {},     # DEPRECATED: Moved to DB
    "settings": {},
    "prompts": {
        "__NOTE__": "CORE IP REMOVED FOR SECURITY. PROMPTS WILL BE AUTO-ENCRYPTED BY SYSTEM."
    }
}

from utils.security import encrypt_dict, decrypt_dict, is_encrypted

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
            
            # Migration: If it was a list (old version) or dict with just 'selected_stocks'
            if isinstance(data, list):
                return {
                    "selected_stocks": data,
                    "positions": {}
                }
            
            # If it's a dict, merge with default
            if isinstance(data, dict):
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                
                # Decrypt Prompts if needed
                prompts = config.get("prompts")
                if prompts and is_encrypted(prompts):
                    try:
                        config["prompts"] = decrypt_dict(prompts)
                    except Exception as e:
                        print(f"Decryption failed: {e}")
                        # Fallback to default prompts if decryption fails provided key is wrong/missing
                        config["prompts"] = DEFAULT_CONFIG["prompts"]
                
                return config
            
            return DEFAULT_CONFIG
    except:
        return DEFAULT_CONFIG

def save_config(config_data):
    # Deep copy to avoid modifying memory state
    import copy
    data_to_save = copy.deepcopy(config_data)
    
    # Encrypt Prompts
    if "prompts" in data_to_save and isinstance(data_to_save["prompts"], dict):
        data_to_save["prompts"] = encrypt_dict(data_to_save["prompts"])
        
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

# load/save_selected_stocks moved to bottom to use DB


def get_position(code):
    return db_get_position(code)

def update_position(code, shares, price, action="buy"):
    """
    Updates position based on action.
    action: 'buy' (calculate weighted avg), 'sell' (reduce shares), 'override' (overwrite)
    PERSISTENCE: SQLite DB ONLY.
    """
    # 1. Get current position from DB
    current = db_get_position(code)
    
    curr_shares = current["shares"]
    curr_cost = current["cost"]
    curr_base = current.get("base_shares", 0)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_shares = curr_shares
    new_cost = curr_cost

    if action == "buy":
        # Weighted Average
        total_value = (curr_shares * curr_cost) + (shares * price)
        new_shares = curr_shares + shares
        # Increase precision to 4 decimals to capture small changes
        new_cost = total_value / new_shares if new_shares > 0 else 0.0
        new_cost = round(new_cost, 4) 
        
        db_update_position(code, int(new_shares), new_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "buy", price, shares, "手动买入")
        
    elif action == "sell":
        # Reducing shares does not change Avg Cost per share (Standard Accounting)
        new_shares = max(0, curr_shares - shares)
        # Cost remains same
        db_update_position(code, int(new_shares), curr_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "sell", price, shares, "手动卖出")
        
    elif action == "override":
        # Direct clean update
        new_shares = int(shares)
        new_cost = round(price, 4)
        
        db_update_position(code, new_shares, new_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "override", price, shares, "持仓修正")

    # 2. No syncing to user_config.json (Deprecated)
    try:
        # Check if code is in DB watchlist, if not add it
        from utils.database import db_get_watchlist, db_add_watchlist
        watchlist = db_get_watchlist()
        if code not in watchlist and new_shares > 0:
             db_add_watchlist(code)
    except Exception as e:
        print(f"Error syncing watchlist: {e}")

def delete_transaction(code: str, timestamp: str):
    """
    Deletes a transaction record by code and timestamp.
    """
    return db_delete_transaction(code, timestamp)

def load_selected_stocks():
    from utils.database import db_get_watchlist
    return db_get_watchlist()

def save_selected_stocks(codes):
    """
    Full sync of watchlist.
    """
    from utils.database import db_get_watchlist, db_add_watchlist, db_remove_watchlist
    current = set(db_get_watchlist())
    target = set(codes)
    
    # Add new
    for c in target - current:
        db_add_watchlist(c)
        
    # Remove old
    for c in current - target:
        db_remove_watchlist(c)

def get_settings():
    config = load_config()
    return config.get("settings", {})

def save_settings(settings_dict):
    config = load_config()
    # Merge with existing settings to avoid overwriting partial updates if needed
    current_settings = config.get("settings", {})
    current_settings.update(settings_dict)
    config["settings"] = current_settings
    save_config(config)

def log_transaction(code: str, action_type: str, price: float = 0.0, volume: float = 0.0, note: str = ""):
    """
    Logs a transaction or configuration change.
    action_type: 'buy', 'sell', 'override', 'allocation'
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_add_history(code, timestamp, action_type, price, volume, note)

def get_history(code: str) -> list:
    return db_get_history(code)

def get_allocation(code: str) -> float:
    return db_get_allocation(code)

def set_allocation(code: str, amount: float):
    old_alloc = db_get_allocation(code)
    db_set_allocation(code, amount)
    
    # Log the change
    if old_alloc != amount:
        log_transaction(code, "allocation", price=0, volume=amount, note=f"Changed from {old_alloc} to {amount}")

def set_base_shares(code: str, shares: int):
    """
    Updates base_shares (Locked Position) in SQLite DB
    """
    # Simply update with dummy cost/shares? No, we need to preserve existing.
    current = db_get_position(code)
    db_update_position(code, current['shares'], current['cost'], base_shares=int(shares))
    
    # Log it
    log_transaction(code, "base_position", price=0, volume=shares, note=f"Set Base Shares to {shares}")
