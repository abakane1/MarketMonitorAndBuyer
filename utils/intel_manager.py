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

def load_intel_db() -> Dict:
    _ensure_dir()
    if not os.path.exists(INTEL_FILE):
        return {}
    try:
        with open(INTEL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_intel_db(db: Dict):
    _ensure_dir()
    with open(INTEL_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def get_claims(code: str) -> List[Dict]:
    db = load_intel_db()
    claims = db.get(code, [])
    # Sort by timestamp descending (Newest Event Date first)
    # Timestamp format is "YYYY-MM-DD HH:MM"
    claims.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return claims

def get_claims_for_prompt(code, hours=None):
    """
    Format claims for LLM prompt.
    If hours is provided, filters by time window.
    If hours is None (default), returns all active claims.
    """
    claims = get_claims(code)
    if not claims:
        return ""
    
    # Sort by time, newest first
    claims.sort(key=lambda x: x['timestamp'], reverse=True)
    
    cutoff = 0
    if hours:
        cutoff = datetime.now().timestamp() - (hours * 3600)
    
    verified_list = []
    false_list = []
    pending_list = []
    
    for c in claims:
        try:
            ts = datetime.strptime(c['timestamp'], "%Y-%m-%d %H:%M").timestamp()
            
            # Filter if hours limit is set
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

def add_claims(code: str, claims: List[any], source: str = "Metaso"):
    """
    Adds claims to the DB.
    'claims' can be:
      - List[str]: Simple strings (uses today as date).
      - List[dict]: Objects like {"content": "...", "date": "YYYY-MM-DD"}.
    Merges with existing entry if one exists for the same DATE.
    """
    db = load_intel_db()
    if code not in db:
        db[code] = []
        
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
    for date_key, texts in claims_by_date.items():
        # Find existing entry for this date
        target_entry = None
        for item in db[code]:
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
                if not target_entry['content'].startswith("•"):
                    target_entry['content'] += "\n" + "\n".join(new_lines)
                else:
                    target_entry['content'] += "\n" + "\n".join(new_lines)
                # Keep the DATE part of timestamp, but maybe update time? 
                # Actually, if we update timestamp to NOW, it changes the sort order to "Recently Updated".
                # But user wants "Event Date" view.
                # If we change timestamp, we lose the "Day" grouping if we rely on timestamp for date.
                # So we must NOT change the DATE part of timestamp.
                # Just update the time part? Or leave it as 00:00?
                # Let's leave it alone to preserve the Event Date key.
                # Or set it to "YYYY-MM-DD 23:59" to show it's new? 
                # Let's keep it consistent.
                pass
                
        else:
            # Create New
            formatted = [f"• [{current_time_str}] {t}" for t in texts]
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "content": "\n".join(formatted),
                "timestamp": f"{date_key} {current_time_str}", # Use current time for creation?
                # But if date_key is "2023-01-01", setting timestamp to "2023-01-01 12:00" is fine.
                "source": source,
                "status": "pending",
                "note": "",
                "distinct_from": []
            }
            db[code].append(new_item)
            
    save_intel_db(db)

def update_claim_status(code: str, claim_id: str, new_status: str, note: str = ""):
    db = load_intel_db()
    if code in db:
        for item in db[code]:
            if item["id"] == claim_id:
                item["status"] = new_status
                if note:
                    item["note"] = note
                break
        save_intel_db(db)

def delete_claim(code: str, claim_id: str):
    db = load_intel_db()
    if code in db:
        db[code] = [item for item in db[code] if item["id"] != claim_id]
        save_intel_db(db)

def mark_claims_distinct(code: str, claim_ids: List[str]):
    """
    Marks a set of claims as mutually distinct (not duplicates).
    Updates each claim's 'distinct_from' list to include the others.
    """
    if len(claim_ids) < 2:
        return
        
    db = load_intel_db()
    if code not in db:
        return
        
    updated = False
    for item in db[code]:
        if item["id"] in claim_ids:
            # Add all other IDs in the set to this item's distinct_from
            current_distinct = set(item.get("distinct_from", []))
            others = set(claim_ids) - {item["id"]}
            if not others.issubset(current_distinct):
                current_distinct.update(others)
                item["distinct_from"] = list(current_distinct)
                updated = True
                
    if updated:
        save_intel_db(db)
