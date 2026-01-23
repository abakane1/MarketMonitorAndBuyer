import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

DATA_DIR = "data"
INTEL_FILE = os.path.join(DATA_DIR, "intelligence.json")

def _ensure_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

from utils.database import db_load_intelligence, db_save_intelligence

def get_claims(code: str) -> List[Dict]:
    # Load List from DB
    # The DB stores the LIST directly as JSON
    data = db_load_intelligence(code)
    # db_load_intelligence returns whatever was stored. Based on migration, it's the list of claims.
    # But wait, db_load_intelligence logic in database.py parses JSON.
    # If `intelligence.json` had `{code: [items]}`, then `intel_data` passed to save was `[items]`.
    # So `data` returned here is `[items]`.
    
    if isinstance(data, list):
        claims = data
    else:
        # Fallback if DB structure is different (e.g. dict wrapper)
        claims = []
        
    # Sort by timestamp descending (Event Date first)
    claims.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return claims

def get_claims_for_prompt(code, hours=None):
    """
    Format claims for LLM prompt.
    If hours is provided, filters by time window (based on entry time).
    Already sorted by get_claims (Event Date desc).
    """
    claims = get_claims(code)
    if not claims:
        return ""
    
    cutoff = 0
    if hours:
        # Use a secondary field or just filter the sorted list.
        # Since timestamp is now EventDate + Time, hours filter might be tricky if it spans years.
        # But for 'Recent' context, we just take the top items.
        cutoff = datetime.now().timestamp() - (hours * 3600)
    
    verified_list = []
    false_list = []
    pending_list = []
    
    for c in claims:
        try:
            # Timestamp is "YYYY-MM-DD HH:MM"
            ts_dt = datetime.strptime(c['timestamp'], "%Y-%m-%d %H:%M")
            ts = ts_dt.timestamp()
            
            # Filter if hours limit is set (relative to current time)
            if hours and ts < cutoff:
                continue

            line = f"- [{c['timestamp']}] {c['content']}"
            if c.get('status') == 'verified':
                verified_list.append(line)
            elif c.get('status') == 'false_info':
                false_list.append(line)
            else:
                pending_list.append(line)
        except:
            continue
            
    sections = []
    if verified_list:
        sections.append("【✅ 用户已人工核实 (绝对事实/Trust User)】:\n" + "\n".join(verified_list))
    if false_list:
        sections.append("【❌ 用户已标记为假 (已辟谣/Ignore)】:\n" + "\n".join(false_list))
    if pending_list:
        sections.append("【⏳ 待验证线索 (需结合下方Search Result判断)】:\n" + "\n".join(pending_list))
        
    return "\n\n".join(sections)

def mark_claims_distinct(code: str, claim_ids: List[str]):
    """
    Marks a set of claims as mutually distinct (not duplicates).
    Updates each claim's 'distinct_from' list to include the others.
    """
    if len(claim_ids) < 2:
        return
        
    current_claims = get_claims(code)
    if not current_claims:
        return
        
    updated = False
    for item in current_claims:
        if item["id"] in claim_ids:
            # Add all other IDs in the set to this item's distinct_from
            current_distinct = set(item.get("distinct_from", []))
            others = set(claim_ids) - {item["id"]}
            if not others.issubset(current_distinct):
                current_distinct.update(others)
                item["distinct_from"] = list(current_distinct)
                updated = True
                
    if updated:
        save_claims_to_db(code, current_claims)
    """
    Adds claims to the DB.
    Merges with existing entry if one exists for the same DATE.
    """
    current_claims = get_claims(code)
    
    current_time_str = datetime.now().strftime("%H:%M")
    
    # Pre-process claims into (date, content) tuples
    processed_claims = []
    
    for c in claims:
        if isinstance(c, dict) and "content" in c:
            # Use provided date or today
            d = c.get("date")
            if not d or len(d) < 10:
                d = datetime.now().strftime("%Y-%m-%d")
            processed_claims.append((d, c["content"]))
        elif isinstance(c, str):
            processed_claims.append((datetime.now().strftime("%Y-%m-%d"), c))
            
    # Group by Date
    claims_by_date = {}
    for d, content in processed_claims:
        if d not in claims_by_date:
            claims_by_date[d] = []
        claims_by_date[d].append(content)
        
    # Process each date group
    updated = False
    
    for date_key, texts in claims_by_date.items():
        # Find existing entry for this date
        target_entry = None
        for item in current_claims:
            if item['timestamp'].startswith(date_key):
                target_entry = item
                break
        
        if target_entry:
            # Append
            new_lines = []
            for text in texts:
                if text in target_entry['content']:
                    continue
                new_lines.append(f"• [{current_time_str}] {text}")
            
            if new_lines:
                target_entry['content'] += "\n" + "\n".join(new_lines)
                target_entry['timestamp'] = f"{date_key} {current_time_str}"
                updated = True
                
        else:
            # Create New
            formatted = [f"• [{current_time_str}] {t}" for t in texts]
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "content": "\n".join(formatted),
                "timestamp": f"{date_key} {current_time_str}", 
                "source": source,
                "status": "pending",
                "note": "",
                "distinct_from": []
            }
            current_claims.append(new_item)
            updated = True
            
    if updated:
        save_claims_to_db(code, current_claims)

def update_claim_status(code: str, claim_id: str, new_status: str, note: str = ""):
    current_claims = get_claims(code)
    updated = False
    for item in current_claims:
        if item["id"] == claim_id:
            item["status"] = new_status
            if note:
                item["note"] = note
            updated = True
            break
    if updated:
        save_claims_to_db(code, current_claims)

def delete_claim(code: str, claim_id: str):
    current_claims = get_claims(code)
    original_len = len(current_claims)
    new_claims = [item for item in current_claims if item["id"] != claim_id]
    
    if len(new_claims) < original_len:
        save_claims_to_db(code, new_claims)

def mark_claims_distinct(code: str, claim_ids: List[str]):
    """
    Marks a set of claims as mutually distinct (not duplicates).
    Updates each claim's 'distinct_from' list to include the others.
    """
    if len(claim_ids) < 2:
        return
        
    current_claims = get_claims(code)
    if not current_claims:
        return
        
    updated = False
    for item in current_claims:
        if item["id"] in claim_ids:
            # Add all other IDs in the set to this item's distinct_from
            current_distinct = set(item.get("distinct_from", []))
            others = set(claim_ids) - {item["id"]}
            if not others.issubset(current_distinct):
                current_distinct.update(others)
                item["distinct_from"] = list(current_distinct)
                updated = True
                
    if updated:
        save_claims_to_db(code, current_claims)
