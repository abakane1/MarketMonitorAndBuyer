
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
        # Sometimes model wraps in ```json ... ```
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
    claims_text = "; ".join(new_claims[:3]) 
    
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
