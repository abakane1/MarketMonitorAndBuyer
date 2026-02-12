# -*- coding: utf-8 -*-
import json
from utils.ai_advisor import call_ai_model

# --- DEFAULT SUB-AGENT PROMPTS ---
# Minimal fallbacks, actual prompts loaded from config

# 1. QUANT AGENT (数学官) - Focus: Numbers, Volume, Flow, Limits
QUANT_SYS = "You are a quantitative analysis engine. Analyze the numerical data and provide objective assessments."

# 2. INTEL AGENT (情报官) - Focus: News, Sentiment, Narrative
INTEL_SYS = "You are a market intelligence analyst. Analyze news and sentiment data to identify market narratives."

def run_blue_legion(code, name, price, api_key_qwen, context_data, prompt_templates=None):
    """
    Executes the Blue Legion (MoE) Strategy Generation.
    Returns: (final_content, final_reasoning, full_context_log)
    """
    
    # 0. Setup
    logs = []
    prompts = prompt_templates or {}
    
    # --- PHASE 1: SUB-AGENTS (Parallel-ish) ---
    # In reality sequential here, but conceptually parallel inputs to Commander
    
    # 1.1 Quant Agent
    # 1.1 Quant Agent
    quant_model = "qwen-max" # Strongest Reasoning
    quant_sys = prompts.get("quant_agent_system", QUANT_SYS)
    
    # Construct Quant User Prompt from Context
    # Incorporate Technicals, Flow, Intraday
    quant_data = f"""
    Trading Date: {context_data.get('date', 'N/A')}
    Market Status: {context_data.get('market_status', 'OPEN')}
    
    Code: {code} ({name})
    Price: {price}
    Limit Up/Down: {context_data.get('limit_up', 'N/A')} / {context_data.get('limit_down', 'N/A')}
    
    [Intraday Summary]
    {context_data.get('intraday_summary', 'N/A')}
    
    [Fund Flow]
    {context_data.get('capital_flow_str', 'N/A')}
    
    IMPORTANT: 如果 Market Status 是 CLOSED，你的所有量化分析必须服务于【下一个交易日 ({context_data.get('date', 'N/A')})】的预判。
    """
    
    q_res, _ = call_ai_model("qwen", api_key_qwen, quant_sys, quant_data, specific_model=quant_model)
    logs.append(f"### [Quant Agent Report ({quant_model})]\n{q_res}")
    
    # 1.2 Intel Agent
    # 1.2 Intel Agent
    intel_model = "qwen-max"
    intel_sys = prompts.get("intel_agent_system", INTEL_SYS)
    
    # Construct Intel User Prompt
    intel_data = f"""
    Trading Date: {context_data.get('date', 'N/A')}
    Market Status: {context_data.get('market_status', 'OPEN')}
    
    Code: {code} ({name})
    
    [Research/News Context]
    {context_data.get('research_context', 'N/A')}
    
    [History Actions]
    {context_data.get('history_log_str', 'N/A')}
    
    IMPORTANT: 如果 Market Status 是 CLOSED，你的情报总结必须侧重于为【下一个交易日 ({context_data.get('date', 'N/A')})】寻找预期差和博弈逻辑。
    """
    
    i_res, _ = call_ai_model("qwen", api_key_qwen, intel_sys, intel_data, specific_model=intel_model)
    logs.append(f"### [Intel Agent Report ({intel_model})]\n{i_res}")
    
    # --- PHASE 2: COMMANDER (Synthesis) ---
    cmd_model = "qwen-max" # The Brain
    
    # Use the standard "LAG + GTO" System Prompt for the Commander
    cmd_sys = prompts.get("proposer_system", "") # Logic is consistent, just brain is Qwen
    if not cmd_sys:
        # Fallback to standard
        cmd_sys = "你是战区最高指挥官。基于量化官和情报官的报告，制定最终作战计划 (LAG+GTO)。"
        
    # Commander User Prompt
    # Matches the structure of `proposer_base` but filled with Agent Reports instead of raw data?
    # Actually, to maintain compatibility with existing Prompts (which expect {price}, {change} etc),
    # We should probably INJECT the Agent Reports into the `research_context` or `intraday_summary` fields 
    # of the existing template?
    # OR create a dedicated Commander User Prompt.
    
    # Let's try to Inject into a new "Legion Context" block.
    
    cmd_user_context = f"""
    *** COMMANDER EYES ONLY ***
    Current Context: {context_data.get('date', 'N/A')} ({context_data.get('market_status', 'OPEN')})
    
    {logs[0]}
    
    {logs[1]}
    
    *** END REPORTS ***
    
    【核心强制指令】：
    1. 当前交易已结束，你签署的【最终执行令 (Final Order)】必须针对【{context_data.get('date', 'N/A')}】生效。
    2. 请在【有效期】字段明确写明执行日期。
    3. 【禁止】不要提供任何针对今日的盘中操作建议（如“做T”、“日内高抛低吸”），因为市场已关闭。
    
    基于以上专家的深度分析，请制定最终交易策略。
    """
    
    # We merge this with the standard Base Prompt Structure to ensure format compliance
    # We can fetch the base template and append our context.
    base_tpl = prompts.get("proposer_base", "{price} {research_context}")
    
    # We override 'research_context' in the context_data to include our reports!
    # This is a clever way to re-use the existing well-tuned prompt structure.
    
    original_rc = context_data.get('research_context', '')
    new_rc = f"{original_rc}\n\n{cmd_user_context}"
    
    # Shallow copy to avoid mutating original for other calls
    cmd_ctx = context_data.copy()
    cmd_ctx['research_context'] = new_rc
    
    try:
        cmd_user_prompt = base_tpl.format(**cmd_ctx)
    except Exception as e:
        cmd_user_prompt = f"Template Error: {e}\n\nContext:\n{cmd_user_context}"
        
    # Call Commander
    final_res, _ = call_ai_model("qwen", api_key_qwen, cmd_sys, cmd_user_prompt, specific_model=cmd_model)
    
    # Qwen doesn't return reasoning, but we can simulate "Reasoning" field with Agent Reports
    legion_reasoning = "\n\n".join(logs)
    
    return final_res, legion_reasoning, cmd_user_prompt, logs


# --- RED LEGION (AUDITOR MOE) ---
# Minimal fallbacks, actual prompts loaded from config

# 3. RED QUANT AUDITOR (数据审计官) - Focus: Validation, Risk, Discrepancies
RED_QUANT_SYS = "You are a risk auditor. Review trading plans and verify numerical accuracy and risk management."

# 4. RED INTEL AUDITOR (情报审计官) - Focus: Fact Check, Narrative consistency
RED_INTEL_SYS = "You are a compliance officer. Verify the logic and narrative consistency of trading strategies."

def run_red_legion(context_data, draft_content, prompt_templates, api_key, model_type="qwen", model_name="qwen-max", is_final=False, kimi_base_url=None):
    """
    Executes the Red Legion (MoE) Strategy Audit.
    Returns: (final_audit_report, full_audit_string)
    """
    code = context_data.get('code')
    name = context_data.get('name')
    price = context_data.get('price')
    
    logs = []
    prompts = prompt_templates or {}
    
    # --- DATA COMPATIBILITY PATCH ---
    # Ensure redundant keys (from ai_advisor) are mapped to keys expected by MoE
    capital_flow = context_data.get('capital_flow_str') or context_data.get('capital_flow', 'N/A')
    daily_stats = context_data.get('daily_stats') or context_data.get('raw_context', 'N/A')
    research_ctx = context_data.get('research_context') or context_data.get('known_info', 'N/A')
    intraday = context_data.get('intraday_summary') or "N/A"

    # --- PHASE 1: SUB-AGENTS ---
    
    # 1.1 Red Quant
    quant_sys = prompts.get("red_quant_auditor_system", RED_QUANT_SYS)
    
    quant_data = f"""
    [Strategy to Audit]
    {draft_content}
    
    [Market Facts]
    Code: {code} ({name})
    Price: {price}
    Fund Flow: {capital_flow}
    Intraday: {intraday}
    Daily Stats: {daily_stats}
    """
    
    q_res, _ = call_ai_model(model_type, api_key, quant_sys, quant_data, specific_model=model_name, base_url=kimi_base_url)
    logs.append(f"### [Red Quant Auditor ({model_name})]\n{q_res}")
    
    # 1.2 Red Intel
    intel_sys = prompts.get("red_intel_auditor_system", RED_INTEL_SYS)
    
    intel_data = f"""
    [Strategy to Audit]
    {draft_content}
    
    [Intelligence Context]
    {research_ctx}
    """
    
    i_res, _ = call_ai_model(model_type, api_key, intel_sys, intel_data, specific_model=model_name, base_url=kimi_base_url)
    logs.append(f"### [Red Intel Auditor ({model_name})]\n{i_res}")
    
    # --- PHASE 2: RED COMMANDER (Verdict) ---
    
    # Default Red Commander System Prompt
    cmd_sys = """
    你是红军最高指挥官 (Red Team Commander)。
    基于【数据审计官】和【情报审计官】的报告，对蓝军策略进行终极裁决。
    
    【裁决标准】：
    1. 如果任一审计官给出 REJECT，则整体倾向于否决。
    2. 如果仅是 WARN，需要提出具体的修改建议。
    3. 如果 PASS，则批准执行。
    
    请输出一份格式化的【审计报告】，包含：
    - 风险评级 (High/Medium/Low)
    - 关键隐患
    - 最终结论 (Approved / Rejected / Needs Revision)
    """
    
    cmd_user_context = f"""
    [Blue Team Strategy]
    {draft_content}
    
    *** AUDIT REPORTS ***
    
    {logs[0]}
    
    {logs[1]}
    
    *** END REPORTS ***
    
    请根据以上审计报告，下达最终裁决。
    """
    
    final_res, _ = call_ai_model(model_type, api_key, cmd_sys, cmd_user_context, specific_model=model_name, base_url=kimi_base_url)
    
    # Combine logs for reasoning display
    full_audit_string = f"{final_res}\n\n" + "\n\n".join(logs)
    
    return final_res, full_audit_string

