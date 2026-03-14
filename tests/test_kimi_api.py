import json
import requests
from utils.config import load_config
from utils.ai_advisor import call_kimi_api

config = load_config()
settings = config.get("settings", {})
key = settings.get("kimi_api_key")
base_url = settings.get("kimi_base_url")
print(f"Key: {key[:8]}..., Base URL: {base_url}")

res, reason = call_kimi_api(key, "You are a helpful assistant.", "Hello!", base_url=base_url)
print("\n=== Result ===")
print("Content:", res)
print("Reasoning:", reason)
