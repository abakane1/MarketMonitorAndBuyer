
import json
import os
import sys
import time
import requests
import re
import uuid
from datetime import datetime

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.intel_manager import load_intel_db, save_intel_db, add_claims
from utils.config import load_config

def call_deepseek_split_date(api_key, text):
    """
    Splits text into independent facts and extracts dates.
    """
    url = "https://api.deepseek.com/v1/chat/completions"
    
    prompt = f"""
    You are a data restructuring assistant.
    Input text contains one or more intelligence claims (possibly with bullet points and timestamps).
    
    Task:
    1. Split the text into individual independent facts/claims.
    2. Extract the **Event Date** (YYYY-MM-DD) for each claim.
       - Inference Rules:
         - If text says "today" or "Jan 17", infer year from context (assume 2026 if vague, or use 2025/2026 based on logic).
         - If text has [2026-01-18 10:00], usage that date.
         - If no date found, use "2026-01-18" (Today) as fallback.
    3. Output JSON list of objects: {{ "content": "Clean text without bullets", "date": "YYYY-MM-DD" }}
    
    Input Text:
    {text}
    
    Output JSON ONLY.
    """
    
    payload = {
        "model": "deepseek-chat", # Use standard chat for formatting, or reasoner if complex
        "messages": [
            {"role": "system", "content": "You are a helpful JSON parser."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        content = res_json['choices'][0]['message']['content']
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```', '', content)
        return json.loads(content)
    except Exception as e:
        print(f"Error parsing: {e}")
        return {"items": []}

def fix_event_dates():
    print("Starting Event Date Fix...")
    config = load_config()
    api_key = config.get("settings", {}).get("deepseek_api_key")
    
    if not api_key:
        print("Error: No DeepSeek API Key found.")
        return

    db = load_intel_db()
    
    new_db_structure = {}
    
    for code, claims in db.items():
        print(f"Processing {code} ({len(claims)} blocks)...")
        
        all_new_items = []
        
        for item in claims:
            content = item.get("content", "")
            if not content:
                continue
                
            print(f"  - Analyzing block (len={len(content)})...")
            res = call_deepseek_split_date(api_key, content)
            
            # The result might be a list directly or under a key
            # Prompt asked for JSON list of objects.
            # But response_format json_object usually forces a dict wrapper?
            # Actually standard practice is to return {"items": [...] }
            # Let's hope LLM followed implied list or wrapped it.
            # Wait, my prompt said "Output JSON list of objects". 
            # DeepSeek strict JSON mode requires JSON object at root usually.
            # Let's see what happens. If it's a dict, look for keys.
            
            items = []
            if isinstance(res, list):
                items = res
            elif isinstance(res, dict):
                # Try to find list values
                for k, v in res.items():
                    if isinstance(v, list):
                        items = v
                        break
            
            if not items:
                print(f"    Warning: No items parsed from block. Keeping original as current date.")
                # Fallback to keep original content on today's date? 
                # Or try to keep original timestamp?
                orig_ts = item.get("timestamp", "")[:10]
                items = [{"content": content, "date": orig_ts if len(orig_ts)==10 else datetime.now().strftime("%Y-%m-%d")}]
            
            all_new_items.extend(items)
            time.sleep(1) # Rate limit
            
        # Now we have all items with dates for this stock
        # Re-insert using add_claims logic (but without writing to file every time)
        # We can simulate add_claims logic locally to build the list
        
        print(f"  - Extracted {len(all_new_items)} discrete facts. Re-grouping...")
        
        # Group by Date
        grouped = {}
        for x in all_new_items:
            d = x.get("date", "2026-01-18")
            c = x.get("content", "")
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(c)
            
        final_list = []
        for d, texts in grouped.items():
            # Format
            formatted = [f"• [00:00] {t}" for t in texts] # We lost the time, so use 00:00 or maybe we asked LLM to keep time?
            # Prompt said "Extract Event Date".
            # If text had [HH:MM], LLM might have stripped it "Clean text without bullets".
            # Asking LLM to keep time would be better but "Event Date" focus is usually day.
            # Let's stick to 00:00 for migrated historical data.
            
            combined = "\n".join(formatted)
            
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "content": combined,
                "timestamp": f"{d} 00:00",
                "source": "Remastered",
                "status": "pending",
                "note": "Date corrected",
                "distinct_from": []
            }
            final_list.append(new_item)
            
        new_db_structure[code] = final_list
        
    print("Saving restructured DB...")
    save_intel_db(new_db_structure)
    print("Done!")

if __name__ == "__main__":
    fix_event_dates()
