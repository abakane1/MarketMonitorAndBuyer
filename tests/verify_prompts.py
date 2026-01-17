import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from utils.config import load_config, CONFIG_FILE

def test_prompt_loading():
    print("--- Testing Prompt Loading ---")
    
    # 1. Check current config
    config = load_config()
    prompts = config.get("prompts", {})
    
    print("Checking if prompts are empty in config.py's DEFAULT_CONFIG...")
    # We can't easily check DEFAULT_CONFIG directly as it's private to config.py 
    # but we can simulate missing user_config.json
    
    if os.path.exists(CONFIG_FILE):
        print(f"Found {CONFIG_FILE}. Content check:")
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            user_data = json.load(f)
            user_prompts = user_data.get("prompts", {})
            for key, val in user_prompts.items():
                if val == prompts.get(key):
                    print(f"  [OK] {key} matches user_config.json")
                else:
                    print(f"  [FAIL] {key} does NOT match user_config.json")
    else:
        print(f"Warning: {CONFIG_FILE} not found. Testing default behavior.")
        for key, val in prompts.items():
            if val == "":
                print(f"  [OK] {key} is empty (as expected for default)")
            else:
                print(f"  [FAIL] {key} is NOT empty: {val[:20]}...")

if __name__ == "__main__":
    test_prompt_loading()
