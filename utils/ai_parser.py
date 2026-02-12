
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
    
    DEFAULT_METASO_PARSER_TEMPLATE = """
    You are an expert financial intelligence analyst.
    
    Task: Extract KEY investment information (claims) from the provided "Report Text".
    
    Context (Existing Knowledge):
    {existing_text}
    
    Report Text (New Search Result):
    {report_text}
    
    Requirements:
    1. Extract new facts, data, rumors, or significant events.
    2. Ignore general market noise or information already present in "Existing Knowledge".
    3. If a new claim contradicts existing knowledge, flag it.
    4. Output MUST be valid JSON.
    
    Output Format:
    {{
        "new_claims": [
            {{ "content": "Specific fact or event...", "date": "YYYY-MM-DD" }}
        ],
        "contradictions": [
             {{ "id": "ID of existing claim", "reason": "Explanation of contradiction" }}
        ]
    }}
    """

    if not report_text or not api_key:
        return {"new_claims": [], "contradictions": []}

    url = "https://api.deepseek.com/v1/chat/completions"
    
    # Format existing claims for context
    existing_text = "\n".join([f"ID:{c['id']} Content:{c['content']}" for c in existing_claims])
    
    if not prompt_template:
        prompt_template = DEFAULT_METASO_PARSER_TEMPLATE
        # return {"new_claims": [], "contradictions": [], "error": "Prompt template missing"}
        
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

def extract_yaml_block(text: str) -> dict:
    """
    Extracts and parses the FIRST YAML block found in the text.
    Blocks are expected to be enclosed in ```yaml ... ```
    """
    if not text:
        return {}
    
    # Try to find yaml block
    match = re.search(r"```yaml\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        # Fallback: maybe it's just a raw yaml-like block if the model is being simple
        # but let's be strict first for accuracy
        return {}
    
    yaml_str = match.group(1).strip()
    
    import yaml # Standard in many environments, or we might need to handle if missing
    try:
        # Using SafeLoader to prevent arbitrary code execution
        return yaml.load(yaml_str, Loader=yaml.SafeLoader)
    except Exception as e:
        print(f"YAML Parse Error: {e}")
        return {}

def parse_strategy_with_fallback(text: str) -> dict:
    """
    Tries to parse strategy using YAML first, then falls back to robust regex patterns.
    Now supports '[xxx]' format and Chinese punctuation.
    """
    structured_data = extract_yaml_block(text)
    
    # Minimal fields we expect
    result = {
        "direction": "观望",
        "price": None,
        "shares": 0,
        "stop_loss": None,
        "take_profit": None,
        "raw_text": text,
        "structured": bool(structured_data)
    }
    
    if structured_data:
        # Map YAML fields to standard app fields
        summary = structured_data.get('summary', {})
        
        # Handle direction mapping
        d = summary.get('direction', result['direction'])
        if "买" in d: d = "买入"
        elif "卖" in d: d = "卖出"
        elif "观" in d: d = "观望"
        elif "持" in d: d = "持有"
        
        result.update({
            "direction": d,
            "price": summary.get('price_range', summary.get('price', None)),
            "shares": summary.get('shares', 0),
            "stop_loss": summary.get('stop_loss'),
            "take_profit": summary.get('take_profit'),
            "data": structured_data # Keep original
        })
    else:
        # --- Robust Regex Fallback ---
        
        # 1. Direction (方向)
        # Matches: 方向: [买入], 方向：买入, 方向: 买入
        dir_match = re.search(r"方向[:：]\s*(\[)?\s*(买入|卖出|观望|持有|做多|做空)", text)
        if dir_match: 
            d = dir_match.group(2)
            if d == "做多": d = "买入"
            if d == "做空": d = "卖出"
            result["direction"] = d
        else:
            # Fallback: Search for 【买入】 style headers
            header_match = re.search(r"【(买入|卖出|观望|持有|做多|做空)】", text)
            if header_match:
                d = header_match.group(1)
                if d == "做多": d = "买入"
                if d == "做空": d = "卖出"
                result["direction"] = d

        # Helper to extract value from patterns like "Key: [Value]" or "Key: Value"
        def extract_val(patterns):
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                if m:
                    # Group 2 is usually the content inside [] or just the value
                    val = m.group(2) if len(m.groups()) >= 2 else m.group(1)
                    return val.replace("[", "").replace("]", "").strip()
            return None

        # 2. Price (建议价格)
        # patterns: 建议价格: [10.5], 建议价格: 10.5-10.6
        result["price"] = extract_val([
            r"建议价格[:：]\s*(\[)?(.*?)(])?(?:\n|$)",
            r"建议区间[:：]\s*(\[)?(.*?)(])?(?:\n|$)"
        ])

        # 3. Shares (建议股数/仓位)
        result["shares"] = extract_val([
            r"(?:建议)?(?:股数|仓位)[:：]\s*(\[)?(.*?)(])?(?:\n|$)"
        ])
        # Try to convert shares to int if possible
        if result["shares"]:
            try:
                # Extract first number found
                num_match = re.search(r"(\d+)", str(result["shares"]))
                if num_match:
                    result["shares"] = int(num_match.group(1))
            except:
                pass

        # 4. Stop Loss (止损)
        result["stop_loss"] = extract_val([
            r"止损(?:价格)?[:：]\s*(\[)?(.*?)(])?(?:\n|$)"
        ])

        # 5. Take Profit (止盈)
        result["take_profit"] = extract_val([
            r"(?:止盈|目标)(?:价格)?[:：]\s*(\[)?(.*?)(])?(?:\n|$)"
        ])
        
    return result
