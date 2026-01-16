import requests
import json
import google.generativeai as genai

def ask_deepseek_advisor(api_key, context_data, research_context="", technical_indicators=None, prompt_templates=None):
    """
    Calls DeepSeek API (Reasoning Model) for short-term trading advice.
    """
    if not api_key:
        return "请在侧边栏设置 DeepSeek API Key。", "", ""

    url = "https://api.deepseek.com/v1/chat/completions"
    
    # 1. Get Templates
    if not prompt_templates:
        prompt_templates = {}
        
    base_tpl = prompt_templates.get("deepseek_base", "")
    research_suffix_tpl = prompt_templates.get("deepseek_research_suffix", "")
    simple_suffix_tpl = prompt_templates.get("deepseek_simple_suffix", "")
    
    # Check if empty (should not happen if config loaded correctly, but fallback safe)
    if not base_tpl:
        return "Error: Prompt templates missing.", "", ""

    # 2. Format Base
    # Safe format using .format(**dict) allows extra keys in dict or missing keys if handled carefully, 
    # but here we should ensure context_data has what we need or use strict formatting.
    # context_data has: name, code, price, support, resistance, signal, reason, quantity, stop_loss
    try:
        base_prompt = base_tpl.format(**context_data)
    except KeyError as e:
        base_prompt = f"Prompt Error: Missing key {e}"

    # 3. Append Suffix
    if technical_indicators and research_suffix_tpl:
        # Prepare data for suffix
        # Suffix expects: macd, kdj, rsi, ma, bollinger, tech_summary, research_context
        suffix_data = {
            "daily_stats": technical_indicators.get('daily_stats', 'N/A'),
            "macd": technical_indicators.get('MACD', 'N/A'),
            "kdj": technical_indicators.get('KDJ', 'N/A'),
            "rsi": technical_indicators.get('RSI(14)', 'N/A'),
            "ma": technical_indicators.get('MA', 'N/A'),
            "bollinger": technical_indicators.get('Bollinger', 'N/A'),
            "tech_summary": technical_indicators.get('signal_summary', 'N/A'),
            "research_context": research_context if research_context else "无情报"
        }
        try:
            base_prompt += research_suffix_tpl.format(**suffix_data)
        except KeyError as e:
            base_prompt += f"\n[Suffix Error: Missing key {e}]"
            
    elif simple_suffix_tpl:
        base_prompt += simple_suffix_tpl

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Use 'deepseek-reasoner' for thinking mode
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": "You are a professional stock trader."},
            {"role": "user", "content": base_prompt}
        ],
        "temperature": 0.6
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            message = res_json['choices'][0]['message']
            
            # Extract content and reasoning
            content = message.get('content', '')
            reasoning = message.get('reasoning_content', '') # DeepSeek specific
            
            return content, reasoning, base_prompt
        else:
            return f"API请求失败: {response.status_code} - {response.text}", "", base_prompt
    except Exception as e:
        return f"请求异常: {str(e)}", "", base_prompt

def ask_gemini_advisor(api_key, context_data, prompt_templates=None):
    """
    Calls Google Gemini API for second opinion.
    """
    if not api_key:
        return "请在侧边栏设置 Gemini API Key。"

    if not prompt_templates:
        prompt_templates = {}
    
    tpl = prompt_templates.get("gemini_base", "")
    if not tpl:
        return "Error: Gemini prompt template missing."
        
    try:
        prompt = tpl.format(**context_data)
    except Exception as e:
        return f"Prompt Format Error: {e}"

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini 请求失败: {str(e)}"
