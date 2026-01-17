import requests
import json

import streamlit as st
from datetime import datetime

@st.cache_data(ttl=1800, show_spinner=False) # Cache for 30 minutes, hide default spinner
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

def ask_metaso_research(api_key: str, base_url: str, context_data: dict, query_template: str = "", query_template_fallback: str = "") -> str:
    """
    Performs deep research using Metaso (秘塔) API.
    Constructs query then calls cached executor.
    """
    if not api_key:
        return "请在侧边栏设置 Metaso API Key。"

    # Remove trailing slash
    base_url = base_url.rstrip("/")
    
    # Construct Query
    if not query_template:
        return "Error: Metaso query template missing."
        
    try:
        query = query_template.format(**context_data)
    except Exception:
        if query_template_fallback:
            try:
                query = query_template_fallback.format(**context_data)
            except:
                query = f"{context_data.get('name')} ({context_data.get('code')}) 最新研报"
        else:
            query = f"{context_data.get('name')} ({context_data.get('code')}) 最新研报" 
    
    # Execute Cached
    return _execute_metaso_query(api_key, base_url, query)

from utils.ai_parser import parse_metaso_report, generate_followup_query

def ask_metaso_research_loop(
    metaso_api_key: str, 
    metaso_base_url: str, 
    deepseek_api_key: str,
    context_data: dict, 
    base_query_template: str, 
    existing_claims: list,
    metaso_parser_template: str,
    max_rounds: int = 3
) -> str:
    """
    Performs multi-round research.
    1. Search.
    2. Extract Claims.
    3. If new claims -> Generate Follow-up Query -> Repeat.
    """
    aggregated_report = ""
    current_claims = existing_claims.copy() # Local working copy
    
    # 1. Initial Query
    try:
        current_query = base_query_template.format(**context_data)
    except:
        current_query = f"{context_data.get('name')} 最新研报"
        
    for r in range(max_rounds):
        # Notify progress if possible (Streamlit specific)
        st.toast(f"🛰️ 正在进行第 {r+1}/{max_rounds} 轮情报搜索...")
        
        # A. Execute Search
        raw_report = _execute_metaso_query(metaso_api_key, metaso_base_url, current_query)
        if not raw_report or "Error" in raw_report:
            break
            
        aggregated_report += f"\n\n=== 第 {r+1} 轮搜索: {current_query} ===\n{raw_report}"
        
        # B. Parse for New Claims (to drive the loop)
        parse_result = parse_metaso_report(deepseek_api_key, raw_report, current_claims, metaso_parser_template)
        new_claims_texts = parse_result.get("new_claims", [])
        
        if not new_claims_texts:
            st.toast("✅ 本轮未发现新情报，搜索结束。")
            break
            
        # Add to local knowledge for next round deduplication
        for nc in new_claims_texts:
            current_claims.append({"id": f"temp_{r}_{hash(nc)}", "content": nc})
            
        # C. Generate Next Query
        if r < max_rounds - 1:
            next_query = generate_followup_query(deepseek_api_key, new_claims_texts, current_query)
            if not next_query:
                break
            current_query = next_query
        else:
            st.toast("⏹️ 达到最大搜索轮次。")
            
    return aggregated_report
