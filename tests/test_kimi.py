import json
import requests
from utils.config import load_config
from utils.ai_advisor import call_kimi_api

original_post = requests.post
def spoofed_post(*args, **kwargs):
    headers = kwargs.get('headers', {})
    headers['User-Agent'] = 'KimiCLI/1.5' 
    kwargs['headers'] = headers
    return original_post(*args, **kwargs)

requests.post = spoofed_post

config = load_config()
settings = config.get("settings", {})
key = settings.get("kimi_api_key")
base_url = "https://api.kimi.com/coding/v1"

print(f"Key: {key[:8]}..., Base URL: {base_url}")

res, reason = call_kimi_api(key, "You are a helpful assistant.", "Hello! Are you there?", base_url=base_url)
print("\n=== Result User-Agent: KimiCLI/1.5 ===")
print("Content:", res)
