import requests
import json
import re

def parse_metaso_report(api_key: str, report_text: str, existing_claims: list) -> dict:
    """
    Uses DeepSeek to:
    1. Extract new claims from the report.
    2. Compare with existing claims.
    3. Identify contradictions.
    
    Returns dict:
    {
        "new_claims": ["claim1", "claim2"],
        "contradictions": [
            {"old_id": "xxx", "old_content": "...", "new_content": "...", "judgement": "Assessment..."}
        ]
    }
    """
    if not report_text or not api_key:
        return {"new_claims": [], "contradictions": []}

    url = "https://api.deepseek.com/v1/chat/completions"
    
    # Format existing claims for context
    existing_text = "\n".join([f"ID:{c['id']} Content:{c['content']}" for c in existing_claims])
    
    prompt = f"""
    You are an Objective Information Extractor.
    
    【Task】
    Extract ONLY Verified News Events, specific Data Points, or Official Announcements.
    Discard all Opinions, Predictions, "Market Sentiment", "Analyst Outlooks", or "Bullish/Bearish" adjectives.
    
    【KNOWN FACTS (Database)】
    {existing_text if existing_text else "None"}
    
    【NEW REPORT (Metaso Search)】
    {report_text}
    
    【Requirements】
    Output a JSON object with two keys:
    1. "new_claims": A list of strings.
       - MUST be objective facts (e.g. "Company released Q3 report", "Stock price hit 10.0").
       - CHECK AGAINST KNOWN FACTS: If a known fact already covers this event/data (semantically similar), DISCARD IT. Do not add duplicates.
       - MUST NOT be analysis (e.g. "Stock looks bullish", "Analysts expect growth").
    2. "contradictions": A list of objects. If a NEW FACT contradicts a KNOWN FACT:
       {{
           "old_id": "ID", 
           "old_content": "...",
           "new_content": "...",
           "judgement": "State conflict objectively."
       }}
    
    CRITICAL: Perform strict semantic deduplication. Do not add redundant info.
    Output pure JSON only.
    """
    
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
        # Sometimes model wraps in ```json ... ```
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```', '', content)
        
        return json.loads(content)
        
    except Exception as e:
        print(f"Parser Error: {e}")
        return {"new_claims": [], "contradictions": []}
