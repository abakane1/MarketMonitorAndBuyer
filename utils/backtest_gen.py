import pandas as pd
from datetime import datetime, time, timedelta
import streamlit as st
import json

from utils.storage import load_minute_data, get_volume_profile, save_research_log, get_latest_strategy_log
from utils.data_fetcher import get_price_precision, aggregate_minute_to_daily, calculate_price_limits, analyze_intraday_pattern
from utils.indicators import calculate_indicators
from utils.config import load_config, get_position, get_allocation
from utils.ai_advisor import build_advisor_prompt, call_deepseek_api
from utils.intel_manager import get_claims_for_prompt
from utils.database import db_get_strategy_logs

def generate_missing_strategy(code: str, name: str, target_date_str: str, current_time_str: str = "09:25:00", **kwargs):
    """
    Generates a strategy for a past date if it doesn't exist.
    'Time Travel': Uses only data available up to target_date + current_time.
    
    Args:
        code: Stock Code
        name: Stock Name
        target_date_str: "YYYY-MM-DD"
        current_time_str: "HH:MM:SS" (e.g. 09:25:00 for pre-market)
        
    Returns:
        dict: The strategy log object (or None if failed)
    """
    
    # 1. Determine Type
    is_pre_market = current_time_str < "09:30:00"
    suffix_key = "proposer_premarket_suffix" if is_pre_market else "proposer_intraday_suffix"
    
    target_dt = datetime.strptime(f"{target_date_str} {current_time_str}", "%Y-%m-%d %H:%M:%S")
    
    # 2. Slice Historical Data (Time Machine)
    # Load ALL minute data
    full_df = load_minute_data(code)
    if full_df.empty:
        return None
        
    # Filter data UP TO target time
    # Note: '时间' column in minute_data is datetime
    # We want data strictly BEFORE the decision point? 
    # For Pre-market (09:25), we want everything up to yesterday close.
    # For Intraday (10:00), we want everything up to today 10:00.
    
    curr_df = full_df[full_df['时间'] <= target_dt].copy()
    if curr_df.empty:
        return None
        
    # Get latest snapshot from this sliced data
    last_bar = curr_df.iloc[-1]
    current_price = last_bar['收盘']
    
    # Pre-close is the close of the PREVIOUS day relative to target_date
    # Find the last day before target_date
    prev_days = curr_df[curr_df['时间'].dt.date < target_dt.date()]
    pre_close = current_price # Default fall back
    if not prev_days.empty:
        pre_close = prev_days.iloc[-1]['收盘']
        
    # 3. Calculate Indicators on Sliced Data
    tech_indicators = calculate_indicators(curr_df)
    # Daily stats aggregation
    tech_indicators["daily_stats"] = aggregate_minute_to_daily(curr_df, precision=get_price_precision(code))
    
    intraday_pattern = "N/A (Pre-market)"
    if not is_pre_market:
        # Analyze today's intraday pattern so far
        today_df = curr_df[curr_df['时间'].dt.date == target_dt.date()]
        if not today_df.empty:
             intraday_pattern = analyze_intraday_pattern(today_df)

    # 4. Context Preparation
    # We need to simulate the 'Positions' state? 
    # For simplicity, we assume generic position info or read from DB current state (which might be wrong for history, but ok for logic)
    # Ideally, we should use the 'real_equity' snapshot but that's complex. 
    # Let's use the current configured Capital/Pos rules but apply to historical price.
    
    # Mocking some context
    pos_data = get_position(code) # Note: This is CURRENT real-time position. 
    # In a perfect backtest we'd pass the simulated position. 
    # However, generating the strategy usually relies on "how much capital I have". 
    # Let's assume standard capital.
    
    total_capital = load_config().get("settings", {}).get("total_capital", 100000.0)
    alloc = get_allocation(code)
    
    # Strategy Algorithm (Volume Profile) - Calculated on Sliced Data
    # We need to re-implement `analyze_volume_profile_strategy` or import it
    from utils.strategy import analyze_volume_profile_strategy
    
    # Volume Profile for Sliced Data
    precision = get_price_precision(code)
    curr_df['price_bin'] = curr_df['收盘'].round(precision)
    vol_profile = curr_df.groupby('price_bin')['成交量'].sum().reset_index().sort_values('price_bin')
    
    strat_res = analyze_volume_profile_strategy(
        current_price, 
        vol_profile, 
        alloc if alloc > 0 else total_capital, 
        0.02, # Risk Pct Mock
        current_shares=0, # Assuming starting fresh or unknown
        proximity_threshold=0.012
    )

    context = {
        "base_shares": 0,
        "tradable_shares": 0,
        "limit_base_price": pre_close,
        "code": code, 
        "name": name, 
        "price": current_price, 
        "pre_close": pre_close,
        "cost": 0, # cost unknown
        "current_shares": 0, 
        "support": strat_res.get('support'), 
        "resistance": strat_res.get('resistance'), 
        "signal": strat_res.get('signal'),
        "reason": strat_res.get('reason'), 
        "quantity": strat_res.get('quantity'),
        "target_position": strat_res.get('target_position', 0),
        "stop_loss": strat_res.get('stop_loss'), 
        "capital_allocation": alloc,
        "total_capital": total_capital, 
        "known_info": get_claims_for_prompt(code) # This is timeless (Knowledge Base)
    }

    # 5. Build Prompt & Call AI (via ExpertRegistry)
    prompts = load_config().get("prompts", {})
    settings = load_config().get("settings", {})
    
    # Map keys for Registry
    api_keys = {
        "deepseek_api_key": settings.get("deepseek_api_key"),
        "qwen_api_key": settings.get("qwen_api_key") or settings.get("dashscope_api_key")
    }
    
    # Model Dispatch
    model_type = kwargs.get("model_type", "DeepSeek")
    from utils.expert_registry import ExpertRegistry
    
    expert = ExpertRegistry.get_expert(model_type, api_keys)
    if not expert:
        return None
        
    tag_prefix = "【历史回补】" if is_pre_market else "【盘中回补】"
    
    # Prepare Prompt/Context depending on Expert ?
    # Expert.propose() interface: propose(context_data, prompt_templates, **kwargs)
    
    # Inject Specific Contexts
    extra_kwargs = {
        "technical_indicators": tech_indicators,
        "intraday_summary": intraday_pattern,
        "suffix_key": suffix_key
    }
    
    # DeepSeek specific context
    if model_type == "DeepSeek":
        extra_kwargs["research_context"] = f"【历史回溯模式 (Backtest Time Travel)】\n当前模拟时间: {target_dt}\n(请基于此时刻以前的数据进行决策)"
        
    # Qwen specific context
    if model_type == "Qwen":
         # QwenExpert expects 'intraday_summary' in context or kwargs (we added it to kwargs)
         # It might need 'capital_flow_str' which is usually pre-formatted.
         # For backtest, we might lack real-time flow data unless we have history.
         # Let's try to fetch history flow if possible?
         # For now, pass a placeholder.
         context['capital_flow_str'] = "N/A (Backtest Mode)"
         context['history_log_str'] = "N/A"
         context['limit_up'] = "N/A"
         context['limit_down'] = "N/A"

    # CALL EXPERT
    final_res = ""
    reasoning = ""
    user_p = ""
    
    try:
        content, r_log, full_prompt, logs = expert.propose(context, prompts, **extra_kwargs)
        
        # Format Result
        final_res = f"{tag_prefix} {content}"
        # If logs returned (e.g. Qwen sub-agents), use them as reasoning
        reasoning = r_log 
        user_p = full_prompt
        
        if "Error" in content or "Request Failed" in content:
            return None
            
    except Exception as e:
        print(f"Expert Propose Error: {e}")
        return None

    # 7. Save to DB using New Function
    from utils.database import db_save_strategy_log
    
    # Save with custom timestamp and model info
    db_save_strategy_log(
        symbol=code,
        prompt=user_p,
        result=final_res,
        reasoning=reasoning,
        model=model_type,
        custom_timestamp=target_dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Return constructed object
    import re
    tag_match = re.search(r"【(.*?)】", final_res)
    tag = tag_match.group(0) if tag_match else "[Backtest-Generated]"
    
    return {
        "timestamp": target_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "result": final_res,
        "reasoning": reasoning,
        "prompt": user_p,
        "tag": tag,
        "model": model_type
    }
