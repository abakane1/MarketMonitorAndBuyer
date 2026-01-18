
import json
import os
import sys
import time
import requests
from typing import List, Dict

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.intel_manager import load_intel_db, save_intel_db
from utils.config import get_settings

def get_deepseek_key():
    settings = get_settings()
    return settings.get("deepseek_api_key")

def call_deepseek_json(api_key, system_prompt, user_prompt):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat", # Use chat for JSON formatting
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['choices'][0]['message']['content']
        else:
            print(f"API Error: {response.text}")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def deduplicate_stock_claims(api_key, stock_code: str, claims: List[Dict]) -> List[str]:
    """
    Returns a list of claim IDs to delete.
    """
    if len(claims) < 2:
        return []

    # Prepare input for LLM
    claims_input = []
    for c in claims:
        claims_input.append({
            "id": c["id"],
            "content": c["content"],
            "timestamp": c["timestamp"]
        })
    
    system_prompt = "You are a helpful assistant that outputs JSON."
    prompt = f"""
    You are a strict data deduplication assistant.
    Below is a list of intelligence claims (JSON).
    
    Task:
    1. Identify items that describe the **same underlying event** or **identical information**.
       - Example of duplicate: 
         A: "[2026-01-17 08:33] Company X invests 50M in Project Y."
         B: "[2026-01-17 10:38] On Jan 17, Company X plans to invest 50M in Project Y."
    2. For each group of duplicates, select **ONE** to KEEP.
       - Preference: The one with the earlier reliable timestamp OR the most complete information.
    3. Return a JSON object with a single key "delete_ids", which is a list of IDs for the items that should be DELETED.
    
    Input Data:
    {json.dumps(claims_input, ensure_ascii=False, indent=2)}
    
    Output Format (JSON only):
    {{
      "delete_ids": ["id_1", "id_2"]
    }}
    If no duplicates found, return: {{ "delete_ids": [] }}
    """

    content = call_deepseek_json(api_key, system_prompt, prompt)
    if content:
        try:
            result = json.loads(content)
            return result.get("delete_ids", [])
        except:
            print("Failed to parse JSON response")
            return []
    return []

def main():
    print("Starting semantic deduplication...")
    
    api_key = get_deepseek_key()
    if not api_key:
        print("DeepSeek API Key not found.")
        return

    db = load_intel_db()
    total_deleted = 0
    
    for code, claims in db.items():
        if not claims:
            continue
            
        print(f"Processing {code} ({len(claims)} items)...")
        delete_ids = deduplicate_stock_claims(api_key, code, claims)
        
        if delete_ids:
            print(f"  - Found {len(delete_ids)} duplicates to delete.")
            original_count = len(db[code])
            
            # Filter out deleted IDs
            db[code] = [c for c in db[code] if c["id"] not in delete_ids]
            
            deleted_count = original_count - len(db[code])
            total_deleted += deleted_count
            print(f"  - Deleted IDs: {delete_ids}")
        else:
            print("  - No duplicates found.")
            
        # Sleep briefly to avoid rate limits if many stocks
        time.sleep(1)

    if total_deleted > 0:
        save_intel_db(db)
        print(f"Deduplication complete. Removed {total_deleted} items.")
    else:
        print("Deduplication complete. No changes made.")

if __name__ == "__main__":
    main()
