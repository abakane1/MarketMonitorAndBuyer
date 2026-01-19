
import requests
import json
import re

def parse_metaso_report(api_key: str, report_text: str, existing_claims: list, prompt_template: str = "") -> dict:
    """
    Uses DeepSeek to:
    1. Extract new claims from the report.
    2. Compare with existing claims.
    3. Identify contradictions.
    """
    if not report_text or not api_key:
        return {"new_claims": [], "contradictions": []}

    url = "https://api.deepseek.com/v1/chat/completions"
    
    # Format existing claims for context
    existing_text = "\n".join([f"ID:{c['id']} Content:{c['content']}" for c in existing_claims])
    
    if not prompt_template:
        return {"new_claims": [], "contradictions": [], "error": "Prompt template missing"}
        
    try:
        prompt = prompt_template.format(existing_text=existing_text if existing_text else "None", report_text=report_text)
    except Exception as e:
        prompt = f"Prompt Format Error: {e}"
    
    payload = {
        "model": "deepseek-chat", # Use standard chat for formatting, or reasoner if complex
        "messages": [
            {"role": "system", "content": "You are a helpful JSON parser."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        content = res_json['choices'][0]['message']['content']
        
        # Parse JSON
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```', '', content)
        
        return json.loads(content)
        
    except Exception as e:
        print(f"Parser Error: {e}")
        return {"new_claims": [], "contradictions": []}

def generate_followup_query(api_key: str, new_claims: list, original_query: str) -> str:
    """
    Generates a follow-up search query based on newly found claims.
    """
    if not new_claims or not api_key:
        return ""
        
    # Limit to top new findings to keep query focused
    # Handle both dict (new format) and string (old format) claims
    claims_to_join = []
    for c in new_claims[:3]:
        if isinstance(c, dict):
            claims_to_join.append(c.get("content", ""))
        else:
            claims_to_join.append(c)
    claims_text = "; ".join(claims_to_join) 
    
    prompt = f"""
    Based on the following new findings from a search:
    "{claims_text}"
    
    The original search objective was: "{original_query}"
    
    Please generate ONE concise search query (max 20 words) to verify details or dig deeper into the most critical/risky part of these new findings.
    Focus on facts, data, or verification of rumors.
    Output ONLY the query string.
    """
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = response.json()
        content = res_json['choices'][0]['message']['content'].strip()
        # Clean quotes
        content = content.replace('"', '').replace("'", "")
        return content
    except Exception as e:
        print(f"Query Gen Error: {e}")
        return ""

def find_duplicate_candidates(api_key: str, claims: list) -> list:
    """
    Identifies potential duplicates using LLM.
    Returns a list of duplicate groups.
    Example return:
    [
        {
            "reason": "Exact same investment event",
            "items": [
                {"id": "1", "content": "..."}, 
                {"id": "2", "content": "..."}
            ],
            "recommended_keep": "1" 
        }
    ]
    """
    if len(claims) < 2:
        return []
        
    claims_input = [{"id": c["id"], "content": c["content"], "timestamp": c["timestamp"]} for c in claims]
    
    prompt = f"""
    You are a data cleaning assistant.
    Analyze the following list of intelligence claims (JSON) to find duplicates.
    
    Definition of Duplicate:
    - Describes the exact same event.
    - Information is redundant.
    - Minor wording differences are duplicates.
    
    Data:
    {json.dumps(claims_input, ensure_ascii=False, indent=2)}
    
    Task:
    1. Group items that are duplicates of each other.
    2. For each group, recommend ONE ID to keep (the one with most detail or best timestamp).
    3. Provide a brief reason.
    
    Output Format (JSON):
    {{
        "groups": [
            {{
                "ids": ["id1", "id2"],
                "reason": "Duplicate investment news",
                "keep_id": "id1"
            }}
        ]
    }}
    If no duplicates, return {{ "groups": [] }}
    """
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful JSON parser."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        content = res_json['choices'][0]['message']['content']
        
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```', '', content)
        
        result = json.loads(content)
        raw_groups = result.get("groups", [])
        
        # Hydrate result with full claim objects for UI
        claim_map = {c["id"]: c for c in claims}
        
        final_groups = []
        for g in raw_groups:
            ids = g.get("ids", [])
            if len(ids) < 2: 
                continue # Skip singletons
                
            # Check for previously confirmed distinct pairs (IGNORE)
            is_ignored = False
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    id_a = ids[i]
                    id_b = ids[j]
                    if id_a in claim_map and id_b in claim_map:
                        item_a = claim_map[id_a]
                        # Check distinct_from list
                        if id_b in item_a.get("distinct_from", []):
                            is_ignored = True
                            print(f"Skipping group (IDs {id_a}, {id_b} marked distinct)")
                            break
                if is_ignored:
                    break
            
            if is_ignored:
                continue

            group_items = [claim_map[id] for id in ids if id in claim_map]
            
            final_groups.append({
                "reason": g.get("reason", "Duplicate"),
                "items": group_items,
                "recommended_keep": g.get("keep_id")
            })
            
        return final_groups
        
    except Exception as e:
        print(f"Dedupe Error: {e}")
        return []

def extract_bracket_content(text: str) -> tuple[str, str]:
    """
    Splits a string like "1234股 (Explanation)" into ("1234股", "Explanation").
    Returns (original_text, "") if no brackets found.
    """
    if not text or text == "N/A" or text == "--":
        return text, ""
    
    # Match something followed by (anything)
    match = re.search(r"^(.*?)\s*\((.*?)\)\s*$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    
    return text.strip(), ""
