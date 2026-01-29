import json
import os
from datetime import datetime
from utils.database import (
    db_get_position, db_update_position, 
    db_get_allocation, db_set_allocation,
    db_get_history, db_add_history, db_delete_transaction
)

CONFIG_FILE = "user_config.json"
PROMPTS_FILE = "prompts_encrypted.json"  # v2.5.1: 分离 Prompts 存储

DEFAULT_CONFIG = {
    # "selected_stocks": [], # DEPRECATED: Moved to DB
    # "positions": {},       # DEPRECATED: Moved to DB
    # "allocations": {},     # DEPRECATED: Moved to DB
    "settings": {},
    "prompts": {
        "__NOTE__": "CORE IP REMOVED FOR SECURITY. PROMPTS WILL BE AUTO-ENCRYPTED BY SYSTEM.",
        "deepseek_noon_suffix": """
# 午间复盘模式 (Noon Review)

## Context
当前时间: {generated_time} (午间休盘时段).
市场完成了上午的交易。

[Morning Session Data]
Current Price (11:30 Close): {price}
Yesterday Final Close: {pre_close}
Morning Change: {change_pct:.2f}%

{capital_flow}

{research_context}

## Task
1. 结合【最新市场情报】与【历史研判】，回顾上午走势特征 (量能/承接).
2. 分析当前持仓 {current_shares} 股的风险.
3. 预判下午开盘后的走势 (下午是延续上涨/下跌，还是反转?).
4. 给下午的操作建议 (Buy/Sell/Hold).

## Output Format
【午间复盘摘要】: ...
【下午预判】: ...
【操作建议】: ...
""",
        "qwen_system": """
你是一家顶尖对冲基金的首席风控官 (CRO)。
你的职责不是生成交易策略，而是对其进行【压力测试】和【风险审计】。
你的性格：多疑、保守、极度厌恶风险。你从不轻信蓝军（策略师）的乐观预测。

你的工作内容：
1. 寻找逻辑漏洞：策略是否基于错误的数据假设？是否忽略了宏观风险？
2. 识别陷阱：这是不是典型的诱多/诱空形态？成交量是否配合？
3. 量化风险：给出一个 0-10 (0=安全, 10=极度危险) 的风险评分。

请用犀利、简练的专业语言进行点评。
""",
        "qwen_audit": """
【审计上下文】
标的: {code} ({name})
当前价格: {price}
市场数据: {daily_stats}

【蓝军策略方案 (待审查)】
{deepseek_plan}

【审计任务】
请作为红军（Red Team）对上述策略进行攻击性审查。如果通过审查，请保持沉默或简单通过；如果发现重大隐患，请大声疾呼。

【输出格式】
1. **风险评分**: X/10 (评分理由)
2. **核心隐患**:
   - [ ] Point 1
   - [ ] Point 2
3. **CRO 最终意见**: (批准执行 / 建议观望 / 强烈否决)
""",
    "refinement_instruction": """
【指令】
你之前生成的策略受到了红军（风控官）的审查。
请仔细阅读红军的【核心隐患】和【CRO 意见】。

【任务】
1. 如果红军指出的风险确实存在，请修正你的原策略（如收紧止损、降低仓位、放弃交易）。
2. 如果你认为红军过于保守，请给出强有力的反驳理由。
3. 输出最终版本的交易计划 (v2.0)。

【红军审查意见】：
{audit_report}
""",
        "deepseek_final_decision": """
【指令】
红军最终裁决如下:
{final_verdict}

请作为蓝军主帅 (Commander)，综合红军意见，签署 **最终执行令 (Final Order)**。
此指令将直接录入交易系统，请确保格式精确。

【必须严格遵循以下输出格式】:
【标的】: [代码] [名称]
【方向】: [买入/卖出/观望/持有/调仓]
【价格】: [具体价格 / 市价 / 对手价]
【数量】: [具体股数 (如 1000股) / 仓位比例 (如 30%)]
【止损】: [具体价格 / 动态]
【止盈】: [具体价格 / 动态]
【有效期】: [仅限今日 / 仅限明日 (如盘后) / 长期]
【决策依据】: [一句话总结 GTO 核心理由]
"""
    }
}

from utils.security import encrypt_dict, decrypt_dict, is_encrypted

def get_stock_profit(symbol: str, current_price: float) -> float:
    """
    Calculates total realized + unrealized profit for a stock.
    Formula: Net Cash Flow (Sell - Buy) + Current Market Value
    """
    # 1. Get History (Buy/Sell) from DB
    # 1. Get History (Buy/Sell/Override) from DB
    # Ensure chronological order (DB query usually sorts it, but to be safe)
    history = db_get_history(symbol)
    history = sorted(history, key=lambda x: x['timestamp'])
    
    net_cash_flow = 0.0
    
    for tx in history:
        t_type = tx['type'].lower()
        price = float(tx['price'])
        amount = float(tx['amount'])
        
        if 'override' in t_type or '修正' in t_type:
             # Override establishes a new basis, effectively resetting previous PnL history.
             # We treat it as a "Virtual Buy" of the new position size at the new cost.
             # Net Cash Flow resets to: -(Shares * Cost)
             # This means "I effectively spent this much to acquire this new position state".
             net_cash_flow = -(amount * price)
             
        elif 'buy' in t_type or '买' in t_type:
            net_cash_flow -= (price * amount)
        elif 'sell' in t_type or '卖' in t_type:
            net_cash_flow += (price * amount)
            
    # 2. Get Current Market Value
    # Note: If history is perfect, db_get_position should match the result of replaying history.
    pos = db_get_position(symbol)
    shares = pos.get('shares', 0)
    market_value = shares * current_price
    
    total_profit = net_cash_flow + market_value
    return total_profit

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
            
            # If it's a dict, merge with default
            if isinstance(data, dict):
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                
                # v2.5.1: Load Prompts from separate file if exists
                if os.path.exists(PROMPTS_FILE):
                    try:
                        with open(PROMPTS_FILE, "r", encoding='utf-8') as pf:
                            prompts_data = json.load(pf)
                            encrypted_prompts = prompts_data.get("prompts")
                            if encrypted_prompts and is_encrypted(encrypted_prompts):
                                config["prompts"] = decrypt_dict(encrypted_prompts)
                    except Exception as e:
                        print(f"Prompts file load error: {e}")
                        config["prompts"] = DEFAULT_CONFIG["prompts"]
                else:
                    # Fallback: Decrypt Prompts from main config (legacy)
                    prompts = config.get("prompts")
                    if prompts and is_encrypted(prompts):
                        try:
                            decrypted = decrypt_dict(prompts)
                            # [PATCH] Merge missing defaults (e.g. new Noon Suffix)
                            defaults = DEFAULT_CONFIG.get("prompts", {})
                            if isinstance(defaults, dict):
                                for k, v in defaults.items():
                                    if k not in decrypted:
                                        decrypted[k] = v
                            config["prompts"] = decrypted
                        except Exception as e:
                            print(f"Decryption failed: {e}")
                            config["prompts"] = DEFAULT_CONFIG["prompts"]
                
                return config
            
            return DEFAULT_CONFIG
            return DEFAULT_CONFIG
    except Exception as e:
        print(f"Config Load Error: {e}")
        # CRITICAL: Do NOT return Default if file exists but read failed.
        # This prevents silent overwriting of valid data with defaults (e.g. wiping API keys).
        # Better to crash/error out than to lose data.
        raise e
        # return DEFAULT_CONFIG

def save_config(config_data):
    # Deep copy to avoid modifying memory state
    import copy
    data_to_save = copy.deepcopy(config_data)
    
    # v2.5.1: Save Prompts to separate file
    if "prompts" in data_to_save and isinstance(data_to_save["prompts"], dict):
        encrypted_prompts = encrypt_dict(data_to_save["prompts"])
        with open(PROMPTS_FILE, "w", encoding='utf-8') as pf:
            json.dump({"prompts": encrypted_prompts, "version": "2.5.1"}, pf, ensure_ascii=False, indent=2)
        # Remove from main config
        del data_to_save["prompts"]
        
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

# load/save_selected_stocks moved to bottom to use DB


def get_position(code):
    return db_get_position(code)

def update_position(code, shares, price, action="buy", custom_date: str = None):
    """
    Updates position based on action.
    action: 'buy' (calculate weighted avg), 'sell' (reduce shares), 'override' (overwrite)
    PERSISTENCE: SQLite DB ONLY.
    """
    # 1. Get current position from DB
    current = db_get_position(code)
    
    curr_shares = current["shares"]
    curr_cost = current["cost"]
    curr_base = current.get("base_shares", 0)
    
    curr_base = current.get("base_shares", 0)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if custom_date:
        timestamp = custom_date
    
    new_shares = curr_shares
    new_cost = curr_cost

    if action == "buy":
        # Weighted Average
        total_value = (curr_shares * curr_cost) + (shares * price)
        new_shares = curr_shares + shares
        # Increase precision to 4 decimals to capture small changes
        new_cost = total_value / new_shares if new_shares > 0 else 0.0
        new_cost = round(new_cost, 4) 
        
        db_update_position(code, int(new_shares), new_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "buy", price, shares, "手动买入")
        
    elif action == "sell":
        # Diluted Cost Method (摊薄成本法)
        # New Total Cost = Current Total Cost - (Sold Shares * Sold Price)
        # Logic: Use the cash back to lower the cost basis of remaining shares.
        current_total_cost = curr_shares * curr_cost
        cash_back = shares * price
        
        new_shares = max(0, curr_shares - shares)
        
        if new_shares > 0:
            new_total_cost = current_total_cost - cash_back
            new_cost = new_total_cost / new_shares
            new_cost = round(new_cost, 4)
        else:
            new_cost = 0.0
            
        db_update_position(code, int(new_shares), new_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "sell", price, shares, "手动卖出")
        
    elif action == "override":
        # Direct clean update
        new_shares = int(shares)
        new_cost = round(price, 4)
        
        db_update_position(code, new_shares, new_cost, base_shares=curr_base)
        db_add_history(code, timestamp, "override", price, shares, "持仓修正")

    # 2. No syncing to user_config.json (Deprecated)
    try:
        # Check if code is in DB watchlist, if not add it
        from utils.database import db_get_watchlist, db_add_watchlist
        watchlist = db_get_watchlist()
        if code not in watchlist and new_shares > 0:
             db_add_watchlist(code)
    except Exception as e:
        print(f"Error syncing watchlist: {e}")

def delete_transaction(code: str, timestamp: str):
    """
    Deletes a transaction record by code and timestamp.
    """
    return db_delete_transaction(code, timestamp)

def load_selected_stocks():
    from utils.database import db_get_watchlist
    return db_get_watchlist()

def save_selected_stocks(codes):
    """
    Full sync of watchlist.
    """
    from utils.database import db_get_watchlist, db_add_watchlist, db_remove_watchlist
    current = set(db_get_watchlist())
    target = set(codes)
    
    # Add new
    for c in target - current:
        db_add_watchlist(c)
        
    # Remove old
    for c in current - target:
        db_remove_watchlist(c)

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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_add_history(code, timestamp, action_type, price, volume, note)

def get_history(code: str) -> list:
    return db_get_history(code)

def get_allocation(code: str) -> float:
    return db_get_allocation(code)

def set_allocation(code: str, amount: float):
    old_alloc = db_get_allocation(code)
    db_set_allocation(code, amount)
    
    # Log the change
    if old_alloc != amount:
        log_transaction(code, "allocation", price=0, volume=amount, note=f"Changed from {old_alloc} to {amount}")

def set_base_shares(code: str, shares: int):
    """
    Updates base_shares (Locked Position) in SQLite DB
    """
    # Simply update with dummy cost/shares? No, we need to preserve existing.
    current = db_get_position(code)
    db_update_position(code, current['shares'], current['cost'], base_shares=int(shares))
    
    # Log it
    log_transaction(code, "base_position", price=0, volume=shares, note=f"Set Base Shares to {shares}")

def save_prompt(key: str, content: str):
    """
    Updates a specific prompt in the config and saves it.
    """
    config = load_config()
    if "prompts" not in config:
        config["prompts"] = {}
    
    config["prompts"][key] = content
    save_config(config)
