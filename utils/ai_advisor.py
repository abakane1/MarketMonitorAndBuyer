import requests
import json
import pandas as pd

from google import genai

def ask_deepseek_advisor(api_key, context_data, research_context="", technical_indicators=None, fund_flow_data=None, fund_flow_history=None, intraday_summary=None, prompt_templates=None, suffix_key="deepseek_research_suffix"):
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
                
                total_main_flow = 0.0
                positive_flow_days = 0
                total_days = len(recent)

                for _, row in recent.iterrows():
                    # Safely get values
                    d = row['日期'].strftime('%m-%d') if hasattr(row['日期'], 'strftime') else str(row['日期'])[:10]
                    c = row.get('收盘价', 0)
                    p = row.get('涨跌幅', 0)
                    if pd.isna(p): p = 0
                    
                    raw_main = row.get('主力净流入-净额', 0)
                    if not pd.isna(raw_main):
                        total_main_flow += float(raw_main)
                        if float(raw_main) > 0:
                            positive_flow_days += 1

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
                
                # 自然语言摘要
                flow_trend = "流入" if total_main_flow > 0 else "流出"
                summary_line = (
                    f"\n【资金统计】近{total_days}日主力累计净{flow_trend} {abs(total_main_flow)/10000:.1f}万。 "
                    f"其中 {positive_flow_days} 天为净流入（占比 {positive_flow_days/total_days:.0%}）。"
                )
                fund_lines.append(summary_line)

            except Exception as e:
                fund_lines.append(f"\n(历史数据格式化错误: {e})")
        
        capital_flow_str = "\n".join(fund_lines) if fund_lines else "N/A"
        
        # 整合分时数据特征
        final_research_context = research_context if research_context else "无情报"
        if intraday_summary:
            final_research_context += f"\n\n[分时盘口特征]\n{intraday_summary}"

        suffix_data = {
            "daily_stats": technical_indicators.get('daily_stats', 'N/A'),
            "macd": technical_indicators.get('MACD', 'N/A'),
            "kdj": technical_indicators.get('KDJ', 'N/A'),
            "rsi": technical_indicators.get('RSI(14)', 'N/A'),
            "ma": technical_indicators.get('MA', 'N/A'),
            "bollinger": technical_indicators.get('Bollinger', 'N/A'),
            "tech_summary": technical_indicators.get('signal_summary', 'N/A'),
            "research_context": final_research_context,
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

    # System Prompt: 注入交易哲学
    system_prompt = (
        "你是一位专业的股票交易员，奉行 'LAG + GTO' 交易哲学。\n"
        "【核心心法】：别人恐惧我贪婪，别人贪婪我恐惧。\n"
        "【分析要求】：在分析时，请极度重视市场情绪的逆向博弈，不要盲从技术指标，要结合对手盘思维。\n"
        "请基于提供的数据（包含资金流向、分时特征、技术指标、市场情报）给出明确的操作建议。"
    )

    # Use 'deepseek-reasoner' for thinking mode
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": system_prompt},
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
