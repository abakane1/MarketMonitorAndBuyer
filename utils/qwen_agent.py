import requests
import json
import re
from datetime import datetime

def search_with_qwen(api_key: str, query: str, model: str = "qwen-max") -> list:
    """
    Calls Qwen (DashScope) with `enable_search=True` to perform a web search.
    Returns a list of intelligence claims (formatted as dicts).
    """
    if not api_key:
        return []

    # DashScope OpenAI Compatible or Native?
    # Using Compatible endpoint with extra body param
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # System Prompt to format output as a list of facts
    system_prompt = """
    你是一个金融情报搜集员。你的任务是利用联网搜索能力，回答用户的查询，并将结果整理为【情报清单】。
    
    要求：
    1. 必须基于最新的搜索结果（Search Results）。
    2. 每一条情报必须包含具体的事实（时间、事件、数据）。
    3. 过滤掉无意义的废话。
    4. 输出格式为 Markdown 列表，每一项以 "- " 开头。
    """

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        "enable_search": True  # Enable DashScope Search
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            
            # Parse the markdown list into intelligence claims
            claims = parse_qwen_response(content)
            return claims
        else:
            print(f"Qwen Search Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"Qwen Request Failed: {e}")
        return []

def parse_qwen_response(text: str) -> list:
    """
    Parses Qwen's markdown response into a list of claim strings.
    """
    lines = text.split('\n')
    claims = []
    import uuid
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for line in lines:
        line = line.strip()
        # Match list items "- " or "* " or "1. "
        if line.startswith("- ") or line.startswith("* ") or re.match(r"^\d+\.", line):
            # Clean marker
            clean_text = re.sub(r"^[-*]\s+|\d+\.\s+", "", line)
            if len(clean_text) > 5: # Ignore too short
                claims.append({
                    "content": clean_text,
                    "date": datetime.now().strftime("%Y-%m-%d") # Default to today
                })
                
    return claims
