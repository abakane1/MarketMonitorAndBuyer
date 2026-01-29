# -*- coding: utf-8 -*-
import json
from utils.ai_advisor import call_ai_model

# --- DEFAULT SUB-AGENT PROMPTS ---

# 1. QUANT AGENT (数学官) - Focus: Numbers, Volume, Flow, Limits
QUANT_SYS = """
你是一台高精度的【金融量化分析引擎】。
你的任务是处理所有输入的数值型数据（资金流向、分时统计、筹码结构、技术指标），并输出一份纯理性的量化评估报告。
【原则】：
1. 只看数字，不带情绪。
2. 重点关注【异常值】（如主力大幅流出但股价不跌、缩量涨停等）。
3. 必须计算盈亏比 (Risk/Reward Ratio) 和胜率估算。

请输出：
【量化评分】(0-100)
【关键支撑/压力位】(基于筹码分布)
【资金博弈结论】(主力是在吸筹、洗盘还是出货？)
"""

# 2. INTEL AGENT (情报官) - Focus: News, Sentiment, Narrative
INTEL_SYS = """
你是华尔街顶级的【市场情报分析师】。
你的任务是阅读所有输入的新闻、公告、研报摘要以及历史交易记录。
【原则】：
1. 识别【叙事逻辑】 (Narrative)：市场现在在炒作什么故事？
2. 判断【预期差】 (Expectation Gap)：消息是利好兑现（Sell the news）还是新升势的起点？
3. 结合历史操作：如果之前多次在该位置失败，必须发出警告。

请输出：
【情绪评分】(-5悲观 ~ +5乐观)
【核心叙事】(一句话概括市场逻辑)
【潜在雷区/催化剂】
"""

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
    quant_model = "qwen-plus" # Balanced/Fast
    quant_sys = prompts.get("blue_quant_sys", QUANT_SYS)
    
    # Construct Quant User Prompt from Context
    # Incorporate Technicals, Flow, Intraday
    quant_data = f"""
    Code: {code} ({name})
    Price: {price}
    Limit Up/Down: {context_data.get('limit_up', 'N/A')} / {context_data.get('limit_down', 'N/A')}
    
    [Intraday Summary]
    {context_data.get('intraday_summary', 'N/A')}
    
    [Fund Flow]
    {context_data.get('capital_flow_str', 'N/A')}
    """
    
    q_res, _ = call_ai_model("qwen", api_key_qwen, quant_sys, quant_data, specific_model=quant_model)
    logs.append(f"### [Quant Agent Report ({quant_model})]\n{q_res}")
    
    # 1.2 Intel Agent
    intel_model = "qwen-plus"
    intel_sys = prompts.get("blue_intel_sys", INTEL_SYS)
    
    # Construct Intel User Prompt
    intel_data = f"""
    Code: {code} ({name})
    
    [Research/News Context]
    {context_data.get('research_context', 'N/A')}
    
    [History Actions]
    {context_data.get('history_log_str', 'N/A')}
    """
    
    i_res, _ = call_ai_model("qwen", api_key_qwen, intel_sys, intel_data, specific_model=intel_model)
    logs.append(f"### [Intel Agent Report ({intel_model})]\n{i_res}")
    
    # --- PHASE 2: COMMANDER (Synthesis) ---
    cmd_model = "qwen-max" # The Brain
    
    # Use the standard "LAG + GTO" System Prompt for the Commander
    cmd_sys = prompts.get("deepseek_system", "") # Logic is consistent, just brain is Qwen
    if not cmd_sys:
        # Fallback to standard
        cmd_sys = "你是战区最高指挥官。基于量化官和情报官的报告，制定最终作战计划 (LAG+GTO)。"
        
    # Commander User Prompt
    # Matches the structure of `deepseek_base` but filled with Agent Reports instead of raw data?
    # Actually, to maintain compatibility with existing Prompts (which expect {price}, {change} etc),
    # We should probably INJECT the Agent Reports into the `research_context` or `intraday_summary` fields 
    # of the existing template?
    # OR create a dedicated Commander User Prompt.
    
    # Let's try to Inject into a new "Legion Context" block.
    
    cmd_user_context = f"""
    *** COMMANDER EYES ONLY ***
    
    {logs[0]}
    
    {logs[1]}
    
    *** END REPORTS ***
    
    基于以上专家的深度分析，请制定最终交易策略。
    """
    
    # We merge this with the standard Base Prompt Structure to ensure format compliance
    # We can fetch the base template and append our context.
    base_tpl = prompts.get("deepseek_base", "{price} {research_context}")
    
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

