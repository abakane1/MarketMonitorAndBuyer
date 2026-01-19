import requests
import json
import pandas as pd

from google import genai

def ask_deepseek_advisor(api_key, context_data, research_context="", technical_indicators=None, fund_flow_data=None, fund_flow_history=None, prompt_templates=None, suffix_key="deepseek_research_suffix"):
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
    # Dynamic suffix fetching
    suffix_tpl = prompt_templates.get(suffix_key, "")
    simple_suffix_tpl = prompt_templates.get("deepseek_simple_suffix", "")
    
    # Check if empty (should not happen if config loaded correctly, but fallback safe)
    if not base_tpl:
        return "Error: Prompt templates missing.", "", ""

    # 2. Format Base
    try:
        base_prompt = base_tpl.format(**context_data)
    except KeyError as e:
        base_prompt = f"Prompt Error: Missing key {e}"

    # 3. Append Suffix
    if technical_indicators and suffix_tpl:
        # Prepare data for suffix
        # Suffix expects: macd, kdj, rsi, ma, bollinger, tech_summary, research_context, capital_flow
        
        # 格式化资金流向数据
        capital_flow_str = "N/A"
        if fund_flow_data and not fund_flow_data.get("error"):
            flow_lines = [f"{k}: {v}" for k, v in fund_flow_data.items()]
            fund_lines = [" | ".join(flow_lines)]
        elif fund_flow_data and fund_flow_data.get("error"):
            fund_lines = [f"当日数据获取失败: {fund_flow_data.get('error')}"]
        else:
            fund_lines = []

        # 格式化历史资金流向 (追加)
        if fund_flow_history is not None and not fund_flow_history.empty:
            try:
                # Limit to last 20 days to save tokens, but give enough trend
                recent = fund_flow_history.tail(20)
                
                table_lines = ["\n**近20交易日资金流向趋势:**", "| 日期 | 收盘 | 涨跌% | 主力净流入(万) | 超大单(万) | 大单(万) |", "|---|---|---|---|---|---|"]
                
                for _, row in recent.iterrows():
                    # Safely get values
                    d = row['日期'].strftime('%m-%d') if hasattr(row['日期'], 'strftime') else str(row['日期'])[:10]
                    c = row.get('收盘价', 0)
                    p = row.get('涨跌幅', 0)
                    if pd.isna(p): p = 0
                    
                    # Convert raw values to Wan
                    def to_wan(v):
                        try:
                            if pd.isna(v): return "0"
                            return f"{float(v)/10000:.0f}"
                        except:
                            return str(v)
                            
                    m_flow = to_wan(row.get('主力净流入-净额', 0))
                    s_flow = to_wan(row.get('超大单净流入-净额', 0))
                    b_flow = to_wan(row.get('大单净流入-净额', 0))
                    
                    table_lines.append(f"| {d} | {c} | {p:.2f} | {m_flow} | {s_flow} | {b_flow} |")
                
                fund_lines.append("\n".join(table_lines))
            except Exception as e:
                fund_lines.append(f"\n(历史数据格式化错误: {e})")
        
        capital_flow_str = "\n".join(fund_lines) if fund_lines else "N/A"
        
        suffix_data = {
            "daily_stats": technical_indicators.get('daily_stats', 'N/A'),
            "macd": technical_indicators.get('MACD', 'N/A'),
            "kdj": technical_indicators.get('KDJ', 'N/A'),
            "rsi": technical_indicators.get('RSI(14)', 'N/A'),
            "ma": technical_indicators.get('MA', 'N/A'),
            "bollinger": technical_indicators.get('Bollinger', 'N/A'),
            "tech_summary": technical_indicators.get('signal_summary', 'N/A'),
            "research_context": research_context if research_context else "无情报",
            "capital_flow": capital_flow_str
        }
        try:
            base_prompt += suffix_tpl.format(**suffix_data)
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
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Gemini 请求失败: {str(e)}"
