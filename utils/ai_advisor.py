import requests
import json
import pandas as pd
from datetime import datetime

from google import genai
from utils.storage import load_production_log
from utils.data_fetcher import calculate_price_limits
from utils.database import db_get_history

def build_advisor_prompt(context_data, research_context="", technical_indicators=None, fund_flow_data=None, fund_flow_history=None, intraday_summary=None, prompt_templates=None, suffix_key="proposer_premarket_suffix", symbol=None):
    """
    Constructs the System Prompt and User Prompt for the AI Advisor.
    Returns: (system_prompt, user_prompt)
    """
    if not prompt_templates: prompt_templates = {}
    
    base_tpl = prompt_templates.get("proposer_base", "")
    suffix_tpl = prompt_templates.get(suffix_key, "")
    simple_suffix_tpl = prompt_templates.get("proposer_simple_suffix", "")
    
    if not base_tpl:
        return "", "Error: Prompt templates missing."

    # [Logic] Phase Determination based on Time
    now = datetime.now()
    hour, minute = now.hour, now.minute
    
    # Define Tunnels
    is_pre_market = (hour < 9) or (hour == 9 and minute < 30)
    is_noon_break = (hour == 11 and minute >= 30) or (hour == 12) or (hour == 13 and minute < 0)
    is_post_market = (hour >= 15) or (hour == 14 and minute >= 55)
    
    if is_post_market:
        shift = 1
        if now.weekday() == 4: shift = 3
        elif now.weekday() == 5: shift = 2
        target_date = now + pd.Timedelta(days=shift)
        context_data['date'] = f"{target_date.strftime('%Y-%m-%d')} (Next Trading Day)"
        context_data['market_status'] = "CLOSED_POST"
    elif is_noon_break:
        context_data['market_status'] = "CLOSED_NOON"
    elif is_pre_market:
        context_data['market_status'] = "PRE_OPEN"
    else:
        # Intraday - Focused on monitoring, not re-planning unless it's a critical node
        context_data['market_status'] = "OPEN_INTRADAY"
        # Optional: Add a note that this is NOT a formal review node
        research_context += "\n【⚠️ 提示】: 当前处于盘中交易时段，建议以观察为主，待午间或盘后再进行正式策略修定。"

    # 2. Format Base
    # Calculate Price Limits
    if 'code' in context_data:
         # [Business Logic] Base Price Selection for Limit Calculation
         m_status = context_data.get('market_status')
         
         if m_status == "CLOSED_POST":
             # Post-market: Forecasting for NEXT Day, use Today's Close as base
             limit_base = float(context_data.get('price', 0))
         else:
             # Pre-market or Noon-market: Working with TODAY's limits, use Yesterday's Close as base
             # Even if 'limit_base_price' is passed from UI, we override it for correctness in NOON mode
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
                history_logs = load_production_log(symbol)
                if history_logs:
                    # 1. Get Trades
                    # 1. Get Trades
                    all_trades = db_get_history(symbol)
                    
                    # STRICT FILTER: Only include explicit Buy/Sell actions.
                    # Exclude 'override', 'correction', 'allocation' to prevent DeepSeek double-counting corrections as new trades.
                    valid_types = ['buy', 'sell']
                    real_trades = []
                    for t in all_trades:
                        t_type = str(t.get('type', '')).strip().lower()
                        if t_type in valid_types and t.get('amount', 0) > 0:
                            # Standardize type for downstream logic
                            t['type'] = t_type 
                            real_trades.append(t)
                    
                    history_context_lines = ["\n[历史研判参考 (Previous AI Analysis & User Execution)]"]
                    
                    logs_asc = sorted(history_logs, key=lambda x: x['timestamp'])
                    # Limit to last 2 to prevent context overflow and distraction
                    recent_subset = logs_asc[-2:] 
                    
                    recent_subset = logs_asc[-2:] 
                    
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
            m_status = context_data.get('market_status')
            if m_status in ["PRE_OPEN", "CLOSED_NOON"]:
                # Pre-market or Noon: Intraday data is from YESTERDAY
                header = "[昨日分时盘口回顾 (Historical/Yesterday's Intraday)]"
            elif m_status == "CLOSED_POST":
                # Post-market: Intraday data is from TODAY
                header = "[今日分时特征总结 (Today's Intraday Reflection)]"
            elif m_status == "OPEN_INTRADAY":
                header = "[盘中实时分时状态]"
            else:
                header = "[分时盘口特征汇要]"
                
            if m_status == "OPEN_INTRADAY":
                final_research_context += f"\n\n{header}: {intraday_summary[:100]}..."
            else:
                final_research_context += f"\n\n{header}\n{intraday_summary}"

        suffix_data = {
            "daily_stats": technical_indicators.get('daily_stats', 'N/A'),
            "macd": technical_indicators.get('MACD', 'N/A'),
            "kdj": technical_indicators.get('KDJ', 'N/A'),
            "rsi": technical_indicators.get('RSI(14)', 'N/A'),
            "ma": technical_indicators.get('MA', 'N/A'),
            "bollinger": technical_indicators.get('Bollinger', 'N/A'),
            "tech_summary": technical_indicators.get('signal_summary', 'N/A'),
            "research_context": final_research_context,
            "capital_flow": capital_flow_str,
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

    # [PATCH] Label Correction for Post-Market
    # Old templates might hardcode "今日交易边界", but in CLOSED state we want "下一个交易日边界"
    if context_data.get('market_status') == 'CLOSED_POST':
        base_prompt = base_prompt.replace("今日交易边界", "下个交易日预计边界")
        base_prompt = base_prompt.replace("今日涨停", "下日涨停").replace("今日跌停", "下日跌停")

    # [OPTIMIZATION] Append Critical State Block at the VERY END for Recency Bias
    # This ensures the AI sees the most important numbers last, reducing calculation errors.
    if context_data:
        p = context_data.get('price', 0)
        cost = context_data.get('avg_cost', context_data.get('cost', 0))
        shares = context_data.get('shares', 0)
        cash = context_data.get('available_cash', 0)
        
        # Calculate max buy/sell for easy reference
        max_buy = int(cash / p) if p > 0 else 0
        max_buy = (max_buy // 100) * 100
        
        profit_pct = ((p - cost) / cost * 100) if cost > 0 else 0
        
        critical_block = f"""
\n################################################################
【🔴 最终决策关键数据 (CRITICAL FACT SHEET) 🔴】
> 请忽略上文任何与此处冲突的数据，以本栏为准进行计算。
当前价格: {p}
持仓数量: {shares} 股
持仓成本: {cost:.3f}
浮动盈亏: {profit_pct:.2f}%
可用资金: {cash:.2f}
最大可买: {max_buy} 股
################################################################
"""
        base_prompt += critical_block

    # System Prompt
    # System Prompt (From Config)
    # System Prompt (From Config)
    # Unified Strategy (LAG + GTO for All)
    sys_key = "proposer_system"
    default_sys = (
        "你那位专业的股票交易员，奉行 'LAG + GTO' 交易哲学。\n"
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

def call_qwen_api(api_key, system_prompt, user_prompt, model="qwen-max"):
    """
    Executes the API call to Qwen (Tongyi Qianwen) via DashScope OpenAI-compatible endpoint.
    """
    if not api_key:
        return "Error: Missing Qwen API Key"

    # DashScope OpenAI Compatible Endpoint
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5 # Conservative for auditing
    }
    
    try:
        # Increased timeout to 120s for complex reasoning
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        print(f"DEBUG: Qwen Status: {response.status_code}")
        if response.status_code != 200: print(f"DEBUG: Qwen Error: {response.text}")
        if response.status_code == 200:
            res_json = response.json()
            if 'choices' in res_json and len(res_json['choices']) > 0:
                content = res_json['choices'][0]['message'].get('content', '')
                return content
            return f"API Error: Empty response format {res_json}"
        else:
            return f"Qwen API Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Qwen Request Failed: {str(e)}"

def build_red_team_prompt(context_data, prompt_templates=None, is_final_round=False):
    """
    Constructs System and User prompts for Red Team Audit.
    is_final_round: If True, this is the 2nd pass (Final Verdict).
    """
    if not prompt_templates: prompt_templates = {}
    
    # Defaults
    DEFAULT_RED_SYS = """
你是一位拥有 20 年经验的【A股德州扑克 LAG + GTO 交易专家】。
你现在担任【策略审计师】(Auditor)，你的交易哲学与蓝军（策略师）完全一致：LAG (松凶) + GTO (博弈论最优)。

你的职责不是无脑反对风险，而是进行【一致性审查】与【纠错】：
1. **去幻觉 (De-Hallucination)**：蓝军引用的数据（如资金流、支撑位）是否真实存在？是否基于事实？
2. **核实逻辑 (Logic Check)**：蓝军的决策是否符合 LAG + GTO 体系？
   - 进攻性检查：在大松凶 (LAG) 信号出现时，蓝军是否足够果断？有没有该买不敢买？
   - 赔率检查：GTO 视角下，这笔交易的 EV (期望值) 是否为正？止损赔率是否合理？

目标：确保蓝军的策略是该体系下的**最优解**。如果不认可，请指出违背了哪条交易原则。
点评风格：像一位严格的德扑教练，一针见血，通过数据和逻辑说话。
"""
    if is_final_round:
        DEFAULT_RED_SYS += "\n【注意】这是**最终轮**审查。如果蓝军已经根据你的前次意见修正了策略，且风险已通过，请直接批准。"

    DEFAULT_RED_USER = """
【审计上下文】
交易日期: {date}
标的: {code} ({name})
当前价格: {price}

【蓝军掌握的情报 (可信事实)】
{daily_stats}

【蓝军策略方案 (待审查)】
{deepseek_plan}

【审计任务】
请以【LAG + GTO 专家】的身份对上述策略进行同行评审 (Peer Review)。
不要做保守的风控官，要做**追求正期望值的赌手教练**。

【输出格式】
1. **真实性核查**: 
   - 蓝军是否捏造了数据？(通过/未通过)
2. **LAG/GTO 体系评估**: 
   - 进攻欲望是否匹配当前牌面？(是/否, 理由)
   - 赔率计算是否合理？
3. **专家最终裁决**: (批准执行 / 建议修正 / 驳回重做)
   - *如果是建议修正，请给出具体的 GTO 调整建议。*
"""
    if is_final_round:
        # Try to get dedicated Final Audit template
        if "reviewer_final_audit" in prompt_templates:
            user_tpl = prompt_templates["reviewer_final_audit"]
            # We don't append the default suffix if we have a custom final template
            # assuming the custom template handles the "Final Round" context.
        else:
            # Fallback to shared audit template + Suffix
            user_tpl = prompt_templates.get("reviewer_audit", DEFAULT_RED_USER)
            user_tpl += "\n【最终裁决要求】这是蓝军修正后的 v2.0 版本。请检查之前的隐患是否消除。如有核心问题未解决，仍可驳回；否则请批准执行。"
    else:
        user_tpl = prompt_templates.get("reviewer_audit", DEFAULT_RED_USER)
        
    sys_tpl = prompt_templates.get("reviewer_system", DEFAULT_RED_SYS)
    
    try:
        user_prompt = user_tpl.format(**context_data)
        if is_final_round and "reviewer_final_audit" not in prompt_templates:
            user_prompt += "\n\n(This is the Final Round Audit for v2.0)"
            
        system_prompt = sys_tpl
        return system_prompt, user_prompt
    except Exception as e:
        return "", f"Prompt Format Error: {e}"

def call_ai_model(model_name, api_key, system_prompt, user_prompt, specific_model=None):
    """
    Unified dispatcher for AI models.
    model_name: "deepseek" or "qwen"
    specific_model: (Optional) specific model ID, e.g. 'qwen-plus', 'qwen-turbo'.
    """
    if model_name == "deepseek":
        # DeepSeek currently hardcoded to 'deepseek-reasoner' inside call_deepseek_api
        # To support switching, we'd need to refactor call_deepseek_api too. 
        # But for now Red Team uses DeepSeek R1 (reasoner) which is correct.
        content, reasoning = call_deepseek_api(api_key, system_prompt, user_prompt)
        return content, reasoning
    elif model_name == "qwen":
        target_model = specific_model if specific_model else "qwen-max"
        content = call_qwen_api(api_key, system_prompt, user_prompt, model=target_model)
        # Qwen returns only content, no reasoning
        return content, ""
    else:
        return f"Error: Unknown Model {model_name}", ""

def ask_qwen_advisor(api_key, context_data, prompt_templates=None):
    """
    Calls Qwen (DashScope) for second opinion (Red Team).
    Legacy wrapper using the new builder.
    """
    sys_p, user_p = build_red_team_prompt(context_data, prompt_templates)
    if "Error" in user_p and sys_p == "":
        return user_p
        
    return call_qwen_api(api_key, sys_p, user_p)

def build_refinement_prompt(original_context, original_plan, audit_report, prompt_templates=None):
    """
    Constructs the Full Prompt for Strategy Refinement.
    """
    if not prompt_templates: prompt_templates = {}
    
    # 1. Reuse Original System Prompt logic (Role persistence)
    # Ideally should match the Blue Team's original system prompt
    sys_key = "proposer_system"
    default_sys = "You are a professional trader."
    system_prompt = prompt_templates.get(sys_key, default_sys)
    
    # 2. Build Refinement Instruction (User Prompt)
    # Default instruction incorporating "Blue Team Autonomy"
    default_refine_instr = """
【来自红军 (审计师) 的反馈】
{audit_report}

【你的任务 / v2.0 迭代】
你是策略专家（蓝军），不是红军的下属。请仔细阅读上述审计意见，并进行**独立判断**：
1. **去伪存真**：如果红军指出的事实错误（如看错数据）确实存在，请修正；如果红军产生了幻觉（错误引用），请在思考中反驳并坚持原判。
2. **吸收建议**：如果红军的 GTO 建议合理（如调整仓位赔率），请优化你的策略。

请输出《交易策略 v2.0 (Refined)》。
- 如果你完全接受红军意见，请修改策略。
- 如果你认为红军错了，请保留原策略并说明理由。
"""
    refine_tpl = prompt_templates.get("refinement_instruction", default_refine_instr)
    
    try:
        user_prompt = refine_tpl.format(audit_report=audit_report)
        
        # MEGA PROMPT CONSTRUCTION:
        # [Context] -> [Plan] -> [Audit] -> [Refine Instruction]
        full_user_prompt = f"""
{original_context}

【前次策略 (Draft v1.0)】
{original_plan}

{user_prompt}
"""
        return system_prompt, full_user_prompt
    except Exception as e:
        return "", f"Refinement Prompt Error: {e}"

def build_final_decision_prompt(aggregated_history: list, prompt_templates=None, context_data=None):
    """
    Constructs the prompt for Step 5: Final Decision using aggregated history.
    aggregated_history: List of strings or dictionaries containing previous steps info.
    """
    if not prompt_templates: prompt_templates = {}
    
    # 1. Extract symbol/name to anchor
    target_info = "当前操作标的"
    if context_data:
        code = context_data.get('code', 'N/A')
        name = context_data.get('name', 'N/A')
        target_info = f"【{code} / {name}】"

    # 2. Aggregating History for Contextual Awareness
    # If the input is just string (legacy fallback), wrap it
    if isinstance(aggregated_history, str):
        history_text = f"【最终审计意见】:\n{aggregated_history}"
    else:
        history_text = "\n\n".join([f"--- 回合 #{i+1} ---\n{step}" for i, step in enumerate(aggregated_history)])

    # 3. System Prompt (Reuse Blue Team)
    sys_key = "proposer_system"
    default_sys = f"你那位专业的股票交易员，奉行 'LAG + GTO' 交易哲学。当前关注标的: {target_info}。"
    system_prompt = prompt_templates.get(sys_key, default_sys)
    
    # 4. User Prompt (Decision Instruction)
    default_instr = f"""
【指令】
以下是针对 {target_info} 进行的 5 个步骤博弈中的前 4 步全量记录（包含初始草案、红军审计、蓝军反思、红军终审）：

{history_text}

请作为蓝军主帅 (Commander)，综合以上【全博弈记录】中的数据、逻辑、分歧点及最终共识，签署该标的的 **最终执行令 (Final Order)**。
【强制锚定】: 请务必确保签署的是 {target_info} 的执行令，严禁提及或受历史参考记录中其他标的（如荣盛发展等）的误导。
此指令将直接录入交易系统，请确保格式精确。

【必须严格遵循以下输出格式】:
【标的】: {target_info}
【方向】: [买入/卖出/观望/持有/调仓]
【价格】: [具体价格]
【数量】: [具体股数]
【止损】: [具体价格]
【止盈】: [具体价格]
【有效期】: [仅限今日/明日/下一交易日]
【决策依据】: [简述理由，需概括前序博弈的关键冲突解决或共识点]
"""
    user_tpl = prompt_templates.get("proposer_final_decision", default_instr)
    
    try:
        # Note: If user_tpl contains other keys, this might need refinement
        user_prompt = user_tpl.format(final_verdict="[Aggregated History Mode]") if "{final_verdict}" in user_tpl else user_tpl
        return system_prompt, user_prompt
    except Exception as e:
        return system_prompt, default_instr # Fallback

def ask_ai_refinement(model_name, api_key, original_context, original_plan, audit_report, prompt_templates=None):
    """
    Asks the Blue Team to refine the strategy based on Red Team audit.
    Legacy wrapper using the new builder.
    """
    if not api_key: return "Error: Missing API Key"
    
    sys_p, user_p = build_refinement_prompt(original_context, original_plan, audit_report, prompt_templates)
    if "Error" in user_p and sys_p == "":
        return user_p, ""
        
    return call_ai_model(model_name, api_key, sys_p, user_p)
