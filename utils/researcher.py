import requests
import json

import streamlit as st
from datetime import datetime

@st.cache_data(ttl=1800) # Cache for 30 minutes
def _execute_metaso_query(api_key: str, base_url: str, query: str) -> str:
    """
    Inner cached executor.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    url_chat = f"{base_url}/chat/completions"
    payload_chat = {
        "model": "metaso-research",
        "messages": [{"role": "user", "content": query}],
        "stream": False
    }
    
    try:
        response = requests.post(url_chat, headers=headers, json=payload_chat, timeout=60)
        if response.status_code == 200:
            res = response.json()
            if 'choices' in res:
                return res['choices'][0]['message']['content']
            elif 'data' in res:
                return res['data']
    except Exception as e:
        print(f"Metaso Chat attempt failed: {e}")
        
    # Search Fallback
    url_search = f"{base_url}/search"
    payload_search = {"query": query, "stream": False}
    try:
        response = requests.post(url_search, headers=headers, json=payload_search, timeout=60)
        if response.status_code == 200:
            res = response.json()
            if 'data' in res:
                return str(res['data'])
            return str(res)
        else:
            return f"Metaso API Error ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Metaso Request Failed: {str(e)}"

def ask_metaso_research(api_key: str, base_url: str, context_data: dict, query_template: str = "") -> str:
    """
    Performs deep research using Metaso (秘塔) API.
    Constructs query then calls cached executor.
    """
    if not api_key:
        return "请在侧边栏设置 Metaso API Key。"

    symbol = context_data.get('code')
    name = context_data.get('name')
    
    # Remove trailing slash
    base_url = base_url.rstrip("/")
    
    # Construct Query
    if not query_template:
        query_template = "分析 {name} ({code}) 近24小时内的最新重大利好利空消息。"
        
    try:
        query = query_template.format(**context_data)
    except Exception:
        query = f"{name} ({symbol}) 最新研报" 
    
    # Execute Cached
    return _execute_metaso_query(api_key, base_url, query)
