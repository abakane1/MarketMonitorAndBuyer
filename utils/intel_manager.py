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
    return db.get(code, [])

def get_claims_for_prompt(code: str, hours: int = 24) -> str:
    """
    Returns a formatted string of relevant claims, grouped by user status.
    """
    claims = get_claims(code)
    if not claims:
        return ""
    
    cutoff = datetime.now().timestamp() - (hours * 3600)
    
    verified_list = []
    false_list = []
    pending_list = []
    
    for c in claims:
        # Include all manually marked items regardless of time? 
        # User said "If user judged... trust user". 
        # False/Verified info is usually persistent, so we should arguably keep them longer than 24h?
        # Let's keep 48h for verified/false, 24h for pending to be safe, or just stick to input param.
        # Let's stick to time window for now to avoid stale info clogging context.
        try:
            ts = datetime.strptime(c['timestamp'], "%Y-%m-%d %H:%M").timestamp()
            if ts > cutoff:
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

def add_claims(code: str, claims: List[str], source: str = "Metaso"):
    """
    Adds simple text claims to the DB.
    """
    db = load_intel_db()
    if code not in db:
        db[code] = []
        
    for text in claims:
        # Basic dedup based on exact string (Improvements: Fuzzy match later)
        # For now, we trust the Parser to do dedup logic potentially
        new_item = {
            "id": str(uuid.uuid4())[:8],
            "content": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": source,
            "status": "pending", # verified, disputed
            "note": ""
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
