import json
import os
from datetime import datetime

CONFIG_FILE = "user_config.json"

DEFAULT_CONFIG = {
    "selected_stocks": [],
    "positions": {},  # Format: "code": {"shares": int, "cost": float}
    "settings": {},
    "allocations": {}, # Format: "code": float (Target Capital)
    "prompts": {
        "deepseek_base": """
    your identity: [A-share Texas Hold'em LAG + GTO Trading Expert] (20 years experience)
    
    【Trading Philosophy: LAG + GTO】
    1. **Loose Aggressive (LAG)**: Play wide ranges (Loose) when odds favor, but attack aggressively (Aggressive) to deny equity and maximize value.
    2. **GTO (Game Theory Optimal)**: 
       - **Balance**: Don't be predictable. Mix "Value Bets" (Confirmed Trend) and "Bluffs" (Anticipated Trend) appropriately.
       - **Indifference**: Set Stop-Loss/Take-Profit such that the market is indifferent to stopping you out vs letting you run (Optimal R:R).
       - **Unexploitable**: Stick to the math (EV). Don't tilt on bad beats (whipsaws).
    3. **Game Thinking**: Every trade is a bet. Only enter when Pot Odds (Risk/Reward) > Equity required.
    
    【Current Hand Data】
    - Symbol: {name} ({code})
    - Price: {price}  (Cost: {cost})
    - Pot Size (Support): {support}
    - Villain Stack (Resistance): {resistance}
    - Signal: {signal} ({reason})
    - Bet Size (Action): {quantity} shares (Target: {target_position}), Exit Line (Fold): {stop_loss}
    (Note: If Exit Line > Cost, it is a Profit Guard/Trailing Stop. If < Cost, it is a Stop Loss.)
    """,
        "deepseek_research_suffix": """
    【技术指标 (Python计算)】
    - 日内数据: {daily_stats}
    - MACD: {macd}
    - KDJ: {kdj}
    - RSI: {rsi}
    - 均线: {ma}
    - 布林带: {bollinger}
    - 信号总结: {tech_summary}
        
    【最新全网研报与新闻情报 (来自秘塔搜索)】
    {research_context}
    
    【任务】
    1. 结合【核心交易数据】（技术面/量化面）与【情报】（基本面/消息面）进行综合研判。
    2. 如果消息面与技术面冲突，请说明风险。
    3. 给出最终操作建议。
        """,
        "deepseek_simple_suffix": """
    【任务】
    1. 深度思考当前盘面逻辑。
    2. 给出明确操作建议（买/卖/观望）。
        """,
        "gemini_base": """
        作为资深A股分析师，请根据以下数据对 {name} ({code}) 进行激进的短线点评：
        
        当前价: {price}
        支撑: {support}
        阻力: {resistance}
        持仓建议: {signal}
        
        请用犀利的语言指出潜在机会或陷阱。
        """,
        "metaso_query": "分析 {name} ({code}) 近24小时内的最新重大利好利空消息、主力资金流向及当前市场情绪。请重点关注短线爆发点和潜在风险，忽略一周前的旧闻。"
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
            
            # Migration: If it was a list (old version) or dict with just 'selected_stocks'
            if isinstance(data, list):
                return {
                    "selected_stocks": data,
                    "positions": {}
                }
            
            # If it's a dict but missing keys, merge with default
            if isinstance(data, dict):
                config = DEFAULT_CONFIG.copy()
                # Ensure 'selected_stocks' is a list if it was a simple dict from old save
                if "selected_stocks" in data:
                    config["selected_stocks"] = data["selected_stocks"]
                if "positions" in data:
                    config["positions"] = data["positions"]
                if "settings" in data:
                    config["settings"] = data["settings"]
                if "prompts" in data:
                    config["prompts"] = data["prompts"]
                return config
            
            return DEFAULT_CONFIG
    except:
        return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

def load_selected_stocks():
    config = load_config()
    return config.get("selected_stocks", [])

def save_selected_stocks(codes):
    config = load_config()
    config["selected_stocks"] = codes
    save_config(config)

def get_position(code):
    config = load_config()
    positions = config.get("positions", {})
    return positions.get(code, {"shares": 0, "cost": 0.0})

def update_position(code, shares, price, action="buy"):
    """
    Updates position based on action.
    action: 'buy' (calculate weighted avg), 'sell' (reduce shares), 'override' (overwrite)
    """
    config = load_config()
    positions = config.get("positions", {})
    current = positions.get(code, {"shares": 0, "cost": 0.0})
    
    curr_shares = current["shares"]
    curr_cost = current["cost"]
    
    if action == "buy":
        # Weighted Average
        total_value = (curr_shares * curr_cost) + (shares * price)
        new_shares = curr_shares + shares
        new_cost = total_value / new_shares if new_shares > 0 else 0.0
        
        positions[code] = {"shares": int(new_shares), "cost": round(new_cost, 2)}
        log_transaction(code, "buy", price=price, volume=shares, note="Manual Buy")
        
    elif action == "sell":
        # Reducing shares does not change Avg Cost per share
        new_shares = max(0, curr_shares - shares)
        positions[code] = {"shares": int(new_shares), "cost": curr_cost} # Cost remains same
        log_transaction(code, "sell", price=price, volume=shares, note="Manual Sell")
        
    elif action == "override":
        # Direct clean update
        positions[code] = {"shares": int(shares), "cost": round(price, 2)}
        log_transaction(code, "override", price=price, volume=shares, note="Position Correction")
        
    config["positions"] = positions
    save_config(config)

def get_settings():
    config = load_config()
    return config.get("settings", {})

def save_settings(settings_dict):
    config = load_config()
    # Merge with existing settings to avoid overwriting partial updates if needed
    current_settings = config.get("settings", {})
    current_settings.update(settings_dict)
    config["settings"] = current_settings
    save_config(config)

def log_transaction(code: str, action_type: str, price: float = 0.0, volume: float = 0.0, note: str = ""):
    """
    Logs a transaction or configuration change.
    action_type: 'buy', 'sell', 'override', 'allocation'
    """
    config = load_config()
    if "history" not in config:
        config["history"] = {}
    if code not in config["history"]:
        config["history"][code] = []
        
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": action_type,
        "price": price,
        "amount": volume, # Use 'amount' for volume/shares or capital allocation value
        "note": note
    }
    config["history"][code].append(entry)
    save_config(config)

def get_history(code: str) -> list:
    config = load_config()
    return config.get("history", {}).get(code, [])

def get_allocation(code: str) -> float:
    config = load_config()
    return config.get("allocations", {}).get(code, 0.0)

def set_allocation(code: str, amount: float):
    config = load_config()
    if "allocations" not in config:
        config["allocations"] = {}
    
    old_alloc = config["allocations"].get(code, 0.0)
    config["allocations"][code] = amount
    save_config(config)
    
    # Log the change
    if old_alloc != amount:
        log_transaction(code, "allocation", price=0, volume=amount, note=f"Changed from {old_alloc} to {amount}")
