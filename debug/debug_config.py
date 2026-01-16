import json
from utils.config import get_settings, load_config

print("--- RAW FILE CONTENT ---")
try:
    with open('user_config.json', 'r') as f:
        print(f.read())
except Exception as e:
    print(f"Error reading file: {e}")

print("\n--- LOADED CONFIG ---")
cfg = load_config()
print(cfg)

print("\n--- GET SETTINGS ---")
settings = get_settings()
print(settings)
