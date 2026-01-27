from utils.ai_advisor import call_deepseek_api
from utils.config import load_config

def get_feedback_metaprompt(daily_result, logs, current_sys_prompt):
    trades_str = "\n".join([f"- {t['time']} {t['action']} {t['shares']}@ {t['price']:.2f} ({t['reason']})" for t in daily_result.get('trades', [])])
    
    logs_str = ""
    for log in logs:
        logs_str += f"- [{log['timestamp']}] {log['result'][:100]}...\n"

    return f"""
# Context
You are an AI Optimization Engine. 
An AI Agent (The "Subject") executed a series of trades today based on its strategies. The day ended with a LOSS.
Your task is to analyze the sequence of decisions vs market reality and suggest a specific improvement to the Subject's System Prompt.

# The Day's Performance
- Status: {daily_result['status']}
- Final PnL: {daily_result['pnl_pct']:.2f}%
- Final Equity: {daily_result['final_equity']:.2f}
- Trades Executed:
{trades_str}

# The AI's Strategy Log (What it was thinking)
{logs_str}

# Root Cause Analysis
- Did the AI buy at the top?
- Did it panic sell at the bottom?
- Did it fail to stop loss?
- Did it flip-flop strategies too often?

# Current System Prompt (Snippet)
```
{current_sys_prompt[:1000]}...
```

# Task
Provide a specific, actionable adjustment to the System Prompt. 
Format:
【问题分析】: (简短分析失败原因)
【优化建议】: (具体的 Prompt 修改建议，例如 "增加xxx约束" 或 "强调xxx逻辑")
"""

# --- New: Human vs AI Battle Review ---
def get_battle_metaprompt(daily_result, logs, real_history, system_prompt):
    """
    Constructs a prompt for analyzing Human (Alpha) vs AI (Beta).
    """
    ai_actions = "\n".join([f"- {t['time']} {t['action']} {t['shares']}@ {t['price']:.2f} ({t['reason']})" for t in daily_result.get('trades', [])])
    
    # Filter real history for this day
    from datetime import datetime
    # We assume real_history is already passed correctly or we parse valid entries
    real_actions_str = ""
    for r in real_history:
        # Simple format
        ts = r.get('timestamp', '') or r.get('time', '')
        t_type = r.get('type', '?')
        px = r.get('price', 0)
        amt = r.get('amount', 0)
        real_actions_str += f"- {ts} {t_type} {amt} @ {px}\n"

    logs_excerpt = ""
    for log in logs[-5:]: # Last 5 decisions
        logs_excerpt += f"--- {log['timestamp']} ---\n{log['result'][:300]}\n"

    return f"""
# Context
You are a Quantitative Trading Coach evaluating a "Human vs AI" battle.
The Human User BEAT the AI Agent today (Alpha > 0). 
Your goal is to identify WHY the Human was smarter and HOW to teach the AI to learn that intuition.

# Performance Comparison
- AI PnL: {daily_result['pnl_pct']:.2f}% (Final Equity: {daily_result['final_equity']:.0f})
- Human PnL: {daily_result['real_pnl_pct']:.2f}% (Final Equity: {daily_result['real_final_equity']:.0f})
- Alpha (User Edge): {daily_result['real_pnl_pct'] - daily_result['pnl_pct']:.2f}%

# Execution Logs
## 🤖 AI Actions (Strictly following logic)
{ai_actions if ai_actions else "(No Trades Executed)"}

## 👤 Human Actions (Real Intuition)
{real_actions_str if real_actions_str else "(No Trades)"}

# AI Logic Stream (Recent thoughts)
{logs_excerpt}

# Current AI System Prompt (Snippet)
```
{system_prompt[:800]}...
```

# Analysis Task
1. **Alpha Source**: What specifically did the user do better? (e.g., Sold earlier, held longer, ignored noise?)
2. **AI Blindspot**: Why did the AI miss this? (e.g., Too conservative, ignored weak signals, lack of 'market sense'?)
3. **Evolution Plan**: Suggest a SPECIFIC instruction to add to the System Prompt to fix this.

# Output Format
【Alpha 来源】: (e.g. 用户在 4.35 提前抢跑卖出，捕捉了流动性)
【AI 盲点】: (e.g. AI 等待右侧确权信号过久，导致回撤)
【进化建议】: (Prompt 修改建议，如 "在盘口高潮时允许左侧止盈...")
"""

def generate_human_vs_ai_review(api_key, daily_result, logs, real_history):
    config = load_config()
    prompts = config.get("prompts", {})
    input_sys = prompts.get("deepseek_base", "N/A")
    
    meta_prompt = get_battle_metaprompt(daily_result, logs, real_history, input_sys)
    
    content, reasoning = call_deepseek_api(
        api_key, 
        system_prompt="You are an expert Trading Coach specializing in RLHF (Reinforcement Learning from Human Feedback).",
        user_prompt=meta_prompt
    )
    return content, reasoning

def generate_prompt_improvement(api_key, daily_result, logs):
    """
    Calls DeepSeek to analyze daily failure.
    """
    config = load_config()
    prompts = config.get("prompts", {})
    input_sys = prompts.get("deepseek_base", "N/A")
    
    meta_prompt = get_feedback_metaprompt(daily_result, logs, input_sys)
    
    content, reasoning = call_deepseek_api(
        api_key, 
        system_prompt="You are an expert Prompt Engineer and Trading Coach.",
        user_prompt=meta_prompt
    )
    return content, reasoning

def get_multi_day_feedback_metaprompt(summary_data, logs, current_sys_prompt):
    """
    summary_data: {
      'ai_pnl': float, 'real_pnl': float, 
      'ai_final': float, 'real_final': float,
      'daily_breakdown': str, (Day 1: AI x, Real y...)
      'ai_trades_count': int,
      'real_trades_count': int
    }
    """
    
    return f"""
# Context
You are a Quantitative Strategy Architect.
We just completed a Multi-Day Backtest (Time Travel Simulation).
Overall Performance:
- AI PnL: {summary_data['ai_pnl']:.2f}% (Final Equity: {summary_data['ai_final']:.0f})
- Human PnL: {summary_data['real_pnl']:.2f}% (Final Equity: {summary_data['real_final']:.0f})
- Alpha (Difference): {summary_data['ai_pnl'] - summary_data['real_pnl']:.2f}%

# Daily Breakdown
{summary_data['daily_breakdown']}

# Current System Prompt (Snippet)
```
{current_sys_prompt[:800]}...
```

# Analysis Task
Compare the performance stability over the period.
1. If AI won: Identify the key strength strategy (e.g. "Better risk control on down days").
2. If AI lost: Identify the structural weakness (e.g. "Over-trading in choppy markets").
3. Suggest a HIGH-LEVEL improvement to the Prompt that applies generally, not just for one specific day.

# Output Format
【周期总结】: (e.g. AI 在震荡期表现优于人类，但在单边下跌中回撤较大)
【优化建议】: (Prompt 具体的修改建议，针对长期稳定性)
"""

def generate_multi_day_review(api_key, summary_data, logs):
    config = load_config()
    prompts = config.get("prompts", {})
    input_sys = prompts.get("deepseek_base", "N/A")
    
    meta_prompt = get_multi_day_feedback_metaprompt(summary_data, logs, input_sys)
    
    content, reasoning = call_deepseek_api(
        api_key, 
        system_prompt="You are an expert Hedge Fund Manager reviewing a weekly strategy report.",
        user_prompt=meta_prompt
    )
    return content, reasoning
