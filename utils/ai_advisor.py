import requests
import json
import pandas as pd

from google import genai
from utils.storage import load_research_log
from utils.data_fetcher import calculate_price_limits
from utils.database import db_get_history

def build_advisor_prompt(context_data, research_context="", technical_indicators=None, fund_flow_data=None, fund_flow_history=None, intraday_summary=None, prompt_templates=None, suffix_key="deepseek_research_suffix", symbol=None):
    """
    Constructs the System Prompt and User Prompt for the AI Advisor.
    Returns: (system_prompt, user_prompt)
    """
    # 1. Get Templates
    if not prompt_templates:
        prompt_templates = {}
        
    base_tpl = prompt_templates.get("deepseek_base", "")
    suffix_tpl = prompt_templates.get(suffix_key, "")
    simple_suffix_tpl = prompt_templates.get("deepseek_simple_suffix", "")
    
    if not base_tpl:
        return "", "Error: Prompt templates missing."

    # 2. Format Base
    # Calculate Price Limits
    # Calculate Price Limits
    if 'code' in context_data:
         # Use explicit base price for limit calc if provided (e.g. for forecasting tomorrow's limits based on today's close)
         # Otherwise default to pre_close (Yesterday's close)
         limit_base = float(context_data.get('limit_base_price', 0))
         
         if limit_base == 0:
             limit_base = float(context_data.get('pre_close', 0))
         if limit_base == 0: 
             limit_base = float(context_data.get('price', 0))
         
         l_up, l_down = calculate_price_limits(
             context_data.get('code', ''),
             context_data.get('name', ''),
             limit_base
         )
         context_data['limit_up'] = l_up
         context_data['limit_down'] = l_down
    else:
         context_data['limit_up'] = "N/A"
         context_data['limit_down'] = "N/A"

    try:
        base_prompt = base_tpl.format(**context_data)
    except KeyError as e:
        base_prompt = f"Prompt Error: Missing key {e}"

    # 3. Append Suffix
    if technical_indicators and suffix_tpl:
        # Prepare data for suffix
        
        # Format Fund Flow
        capital_flow_str = "N/A"
        if fund_flow_data and not fund_flow_data.get("error"):
            flow_lines = [f"{k}: {v}" for k, v in fund_flow_data.items()]
            fund_lines = [" | ".join(flow_lines)]
        elif fund_flow_data and fund_flow_data.get("error"):
            fund_lines = [f"当日数据获取失败: {fund_flow_data.get('error')}"]
        else:
            fund_lines = []

        # Format History Fund Flow
        if fund_flow_history is not None and not fund_flow_history.empty:
            try:
                recent = fund_flow_history.tail(20)
                table_lines = ["\n**近20交易日资金流向趋势:**", "| 日期 | 收盘 | 涨跌% | 主力净流入(万) | 超大单(万) | 大单(万) |", "|---|---|---|---|---|---|"]
                
                total_main_flow = 0.0
                positive_flow_days = 0
                total_days = len(recent)

                for _, row in recent.iterrows():
                    d = row['日期'].strftime('%m-%d') if hasattr(row['日期'], 'strftime') else str(row['日期'])[:10]
                    c = row.get('收盘价', 0)
                    p = row.get('涨跌幅', 0)
                    if pd.isna(p): p = 0
                    
                    raw_main = row.get('主力净流入-净额', 0)
                    if not pd.isna(raw_main):
                        total_main_flow += float(raw_main)
                        if float(raw_main) > 0:
                            positive_flow_days += 1

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
                
                flow_trend = "流入" if total_main_flow > 0 else "流出"
                summary_line = (
                    f"\n【资金统计】近{total_days}日主力累计净{flow_trend} {abs(total_main_flow)/10000:.1f}万。 "
                    f"其中 {positive_flow_days} 天为净流入（占比 {positive_flow_days/total_days:.0%}）。"
                )
                fund_lines.append(summary_line)

            except Exception as e:
                fund_lines.append(f"\n(历史数据格式化错误: {e})")
        
        capital_flow_str = "\n".join(fund_lines) if fund_lines else "N/A"
        
        # Format RAG Context (History + Execution)
        final_research_context = research_context if research_context else "无情报"
        
        if symbol:
            try:
                history_logs = load_research_log(symbol)
                if history_logs:
                    # 1. Get Trades
                    all_trades = db_get_history(symbol)
                    real_trades = [t for t in all_trades if t['type'] in ['buy', 'sell'] and t.get('amount', 0) > 0]
                    
                    history_context_lines = ["\n[历史研判参考 (Previous AI Analysis & User Execution)]"]
                    
                    logs_asc = sorted(history_logs, key=lambda x: x['timestamp'])
                    recent_subset = logs_asc[-3:] 
                    
                    from datetime import datetime
                        
                    import re
                    for idx, log in enumerate(recent_subset):
                        h_ts = log.get('timestamp', 'N/A')
                        h_res = log.get('result', '')
                        
                        # Extract ONLY the Decision Summary to save tokens and avoid hallucination from old reasoning
                        summary_match = re.search(r"【决策摘要】(.*)", h_res, re.DOTALL)
                        if summary_match:
                             clean_res = "【决策摘要】" + summary_match.group(1).strip()
                        else:
                             clean_res = h_res[:200] + "..." if len(h_res) > 200 else h_res

                        entry_header = f"\n--- History #{idx+1} ({h_ts}) ---"
                        history_context_lines.append(entry_header)
                        history_context_lines.append(f"{clean_res}")
                        
                        start_time = h_ts
                        full_idx = logs_asc.index(log)
                        if full_idx < len(logs_asc) - 1:
                            end_time = logs_asc[full_idx+1]['timestamp']
                        else:
                            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                        matched_tx = []
                        for t in real_trades:
                            # Parse timestamp string to datetime object for comparison if needed, 
                            # but assuming strings work if format is consistent ISO
                            if start_time <= t['timestamp'] < end_time:
                                 action = "买入" if t['type'] == 'buy' else "卖出"
                                 matched_tx.append(f"{action} {int(t['amount'])}股 @ {t['price']}")
                        
                        if matched_tx:
                             history_context_lines.append(f"【⚠️ 用户实际执行 (User Action)】: {'; '.join(matched_tx)}")
                        else:
                             history_context_lines.append(f"【用户实际执行】: (无操作 / No Action)")

                        # SKIP Reasoning to prevent context pollution
                    
                    # Add Disclaimer
                    history_context_lines.append(f"\n[Important]: 以上是历史数据。当前最新价格请以顶部【当前手牌数据】为准 ({context_data.get('price', 'Unknown')})。")
                    
                    final_research_context += "\n" + "\n".join(history_context_lines)
            except Exception as e:
                print(f"Error loading history for RAG: {e}")

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
        # Merge context_data to provide access to 'price', 'code', 'name' etc. in suffix
        if context_data:
            suffix_data.update(context_data)
        try:
            base_prompt += suffix_tpl.format(**suffix_data)
        except KeyError as e:
            base_prompt += f"\n[Suffix Error: Missing key {e}]"
            
    elif simple_suffix_tpl:
        base_prompt += simple_suffix_tpl

    # System Prompt
    # System Prompt (From Config)
    # System Prompt Logic (ETF vs Stock)
    is_etf = False
    if symbol:
        # Simple heuristic for China market ETFs: 51xxxx (SH), 15xxxx (SZ), 58xxxx (KCB ETF)
        # Note: 588xxx is usually 科创50ETF
        if symbol.startswith(('51', '15', '58')):
            is_etf = True
            
    if is_etf:
        # Use ETF Strategy
        sys_key = "deepseek_system_etf"
        default_sys = (
            "你那位全球宏观趋势交易者 + 网格策略专家。\n"
            "【核心】: ETF 代表一篮子资产。请忽略个股黑天鹅，专注于宏观趋势、行业景气度与资金流向分析。\n"
            "【策略】: 趋势跟踪 (Trend Following) + 网格波动套利 (Grid Trading)。"
        )
    else:
        # Use Stock Strategy
        sys_key = "deepseek_system"
        default_sys = (
            "你是一位专业的股票交易员，奉行 'LAG + GTO' 交易哲学。\n"
            "【核心心法】：别人恐惧我贪婪，别人贪婪我恐惧。\n"
            "请基于提供的数据（包含资金流向、分时特征、技术指标、市场情报以及历史研判记录）给出明确的操作建议。"
        )
        
    system_prompt = prompt_templates.get(sys_key, default_sys)
    
    return system_prompt, base_prompt

def call_deepseek_api(api_key, system_prompt, user_prompt):
    """
    Executes the API call to DeepSeek.
    """
    if not api_key:
        return "Error: Missing API Key", ""

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.6
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        if response.status_code == 200:
            res_json = response.json()
            message = res_json['choices'][0]['message']
            content = message.get('content', '')
            reasoning = message.get('reasoning_content', '')
            return content, reasoning
        else:
            return f"API Error {response.status_code}: {response.text}", ""
    except Exception as e:
        return f"Request Failed: {e}", ""

def ask_deepseek_advisor(api_key, context_data, research_context="", technical_indicators=None, fund_flow_data=None, fund_flow_history=None, intraday_summary=None, prompt_templates=None, suffix_key="deepseek_research_suffix", symbol=None):
    """
    Wrapper for backward compatibility.
    """
    sys_p, user_p = build_advisor_prompt(
        context_data, research_context, technical_indicators, 
        fund_flow_data, fund_flow_history, intraday_summary, 
        prompt_templates, suffix_key, symbol
    )
    
    if "Error" in user_p and sys_p == "":
        return user_p, "", ""
        
    content, reasoning = call_deepseek_api(api_key, sys_p, user_p)
    return content, reasoning, user_p

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
