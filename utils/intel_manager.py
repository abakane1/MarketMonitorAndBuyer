import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from utils.database import db_load_intelligence, db_save_intelligence

def _parse_sort_key(ts: str) -> str:
    """
    从 timestamp 中提取可排序的日期字符串。
    兼容格式:
      - "2026-02-11 22:06"  -> "2026-02-11 22:06"
      - "近期(2026-01-20) 22:28" -> "2026-01-20 22:28"
      - 其他异常格式 -> "0000-00-00 00:00" (排到末尾)
    """
    if not ts:
        return "0000-00-00 00:00"
    
    # 尝试提取括号中的日期: "近期(YYYY-MM-DD) HH:MM"
    m = re.search(r'(\d{4}-\d{2}-\d{2})\)?\s*(\d{2}:\d{2})?', ts)
    if m:
        date_part = m.group(1)
        time_part = m.group(2) or "00:00"
        return f"{date_part} {time_part}"
    
    return "0000-00-00 00:00"

def get_claims(code: str) -> List[Dict]:
    """
    从数据库加载情报列表
    """
    data = db_load_intelligence(code)
    if isinstance(data, list):
        claims = data
    else:
        claims = []
        
    # 按时间戳从新到旧排序（兼容异常格式）
    claims.sort(key=lambda x: _parse_sort_key(x.get("timestamp", "")), reverse=True)
    return claims

def save_claims_to_db(code: str, claims: List[Dict]):
    """
    保存情报列表到数据库
    """
    db_save_intelligence(code, claims)

def get_claims_for_prompt(code: str, hours: Optional[int] = None) -> str:
    """
    为 LLM 提示词格式化情报数据
    """
    claims = get_claims(code)
    if not claims:
        return ""
    
    cutoff = 0
    if hours:
        cutoff = datetime.now().timestamp() - (hours * 3600)
    
    verified_list = []
    false_list = []
    pending_list = []
    user_manual_list = []
    
    for c in claims:
        try:
            # 时间戳格式 "YYYY-MM-DD HH:MM"
            ts_dt = datetime.strptime(c['timestamp'], "%Y-%m-%d %H:%M")
            ts = ts_dt.timestamp()
            
            if hours and ts < cutoff:
                continue

            line = f"- [{c['timestamp']}] {c['content']}"
            
            # Special handling for User Manual Input
            if c.get('source') == 'UserManual':
                user_manual_list.append(line)
                continue
                
            if c.get('status') == 'verified':
                verified_list.append(line)
            elif c.get('status') == 'false_info':
                false_list.append(line)
            else:
                pending_list.append(line)
        except:
            continue
            
    sections = []
    if user_manual_list:
        sections.append("【🚨 核心情报 (用户强制输入/Critical Info - HIGHEST PRIORITY)】:\n" + "\n".join(user_manual_list))
    if verified_list:
        sections.append("【✅ 用户已人工核实 (绝对事实/Trust User)】:\n" + "\n".join(verified_list))
    if false_list:
        sections.append("【❌ 用户已标记为假 (已辟谣/Ignore)】:\n" + "\n".join(false_list))
    if pending_list:
        sections.append("【⏳ 待验证线索 (需结合下方Search Result判断)】:\n" + "\n".join(pending_list))
        
    return "\n\n".join(sections)

def add_claims(code: str, claims: List[any], source: str = "Metaso"):
    """
    添加新情报到数据库，按日期合并
    """
    current_claims = get_claims(code)
    current_time_str = datetime.now().strftime("%H:%M")
    
    processed_claims = []
    for c in claims:
        if isinstance(c, dict) and "content" in c:
            d = c.get("date")
            if not d or len(d) < 10:
                d = datetime.now().strftime("%Y-%m-%d")
            processed_claims.append((d, c["content"]))
        elif isinstance(c, str):
            processed_claims.append((datetime.now().strftime("%Y-%m-%d"), c))
            
    claims_by_date = {}
    for d, content in processed_claims:
        if d not in claims_by_date:
            claims_by_date[d] = []
        claims_by_date[d].append(content)
        
    updated = False
    for date_key, texts in claims_by_date.items():
        target_entry = None
        # Don't merge if source is UserManual (keep them distinct for visibility)
        if source != "UserManual":
            for item in current_claims:
                if item['timestamp'].startswith(date_key) and item.get('source') == source:
                    target_entry = item
                    break
        
        if target_entry:
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
            formatted = [f"• [{current_time_str}] {t}" for t in texts]
            
            # Auto-verify UserManual
            init_status = "verified" if source == "UserManual" else "pending"
            
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "content": "\n".join(formatted),
                "timestamp": f"{date_key} {current_time_str}", 
                "source": source,
                "status": init_status,
                "note": "",
                "distinct_from": []
            }
            current_claims.append(new_item)
            updated = True
            
    if updated:
        save_claims_to_db(code, current_claims)

def update_claim_status(code: str, claim_id: str, new_status: str, note: str = ""):
    """
    更新情报状态（如标记为核实或伪造）
    """
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
    """
    删除一条情报
    """
    current_claims = get_claims(code)
    original_len = len(current_claims)
    new_claims = [item for item in current_claims if item["id"] != claim_id]
    
    if len(new_claims) < original_len:
        save_claims_to_db(code, new_claims)

def mark_claims_distinct(code: str, claim_ids: List[str]):
    """
    标记情报为互斥（非重复）
    """
    if len(claim_ids) < 2:
        return
        
    current_claims = get_claims(code)
    if not current_claims:
        return
        
    updated = False
    for item in current_claims:
        if item["id"] in claim_ids:
            current_distinct = set(item.get("distinct_from", []))
            others = set(claim_ids) - {item["id"]}
            if not others.issubset(current_distinct):
                current_distinct.update(others)
                item["distinct_from"] = list(current_distinct)
                updated = True
                
    if updated:
        save_claims_to_db(code, current_claims)
