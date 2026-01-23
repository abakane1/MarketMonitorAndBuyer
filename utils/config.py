import json
import os
from datetime import datetime
from utils.database import (
    db_get_position, db_update_position, 
    db_get_allocation, db_set_allocation,
    db_get_history, db_add_history, db_delete_transaction
)

CONFIG_FILE = "user_config.json"

DEFAULT_CONFIG = {
    "selected_stocks": [],
    "positions": {},  # Format: "code": {"shares": int, "cost": float}
    "settings": {},
    "allocations": {}, # Format: "code": float (Target Capital)
    "prompts": {
        "deepseek_base": """
    你的身份: [A股德州扑克 LAG + GTO 交易专家] (20年经验)
    
    【交易哲学: LAG + GTO】
    1. **松凶 (LAG)**: 赔率有利时打法奔放；一旦锁定趋势则暴力进攻，压制对手赔率并最大化价值。
    2. **GTO (博弈最优策略)**: 
       - **平衡**: 混合“价值注”（确认趋势）和“诈唬”（预期趋势），让市场无法预测。
       - **无差别**: 设置止损/止盈，使市场在止损你和任你运行之间处于无差别状态（最优损益比）。
       - **不可被剥削**: 严格遵守数学期望值（EV），不在波动（洗盘）中产生情绪偏离。
    3. **博弈思维**: 每笔交易都是一次下注。仅在 胜率 * 赔率 > 1 时入场。
    4. **反人性心态**: 别人恐惧我贪婪，别人贪婪我恐惧。在恐慌盘涌出时寻找流动性（接飞刀），在情绪高潮时提供流动性（止盈）。
    
    【当前手牌数据】
    - 股票名称: {name} ({code})
    - 当前价格: {price}  (持仓成本: {cost})
    - 底池大小 (支撑位): {support}
    - 对手筹码 (阻力位): {resistance}
    - 信号: {signal} ({reason})
    - 计算依据: 本股资金限额 {capital_allocation} 元, 总资金 {total_capital} 元, 当前持有 {current_shares} 股。
    - 下注大小 (动作): {quantity} 股 (目标总持仓: {target_position} 股), 弃牌线 (止损): {stop_loss}
    (注: 如果 止损线 > 成本，则为盈利保护/移动止盈；如果 < 成本，则为原始止损。)
    """,
        "deepseek_research_suffix": """
    【技术指标 (Python计算)】
    - 历史行情 (日线): \n{daily_stats}
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
    2. 如果消息面与技术面冲突，请重点说明风险。
    3. 给出最终的操作建议。
    4. **特别要求**: 在【决策摘要】中，必须明确给出“建议股数” (具体整数，如 200) 而不是百分比比例。
       - 格式要求: `建议股数: [具体数字]` (示例: `建议股数: 500`)
       - 参考根据: 根据“本股资金限额”和“当前价格”计算出该持有的总股数，再减去“当前持有”得出本次应操作的股数。
    """,
        "deepseek_simple_suffix": """
    【任务】
    1. 深度思考当前盘面逻辑。
    2. 给出明确操作建议（买/卖/观望）。
    """,
        "gemini_base": """
        As a senior A-share investment strategist, please provide an aggressive short-term analysis of {name} ({code}) based on the following data:
        
        Current Price: {price}
        Support: {support}
        Resistance: {resistance}
        Signal: {signal}
        
        Using sharp and professional language, identify hidden opportunities or potential "traps." Focus on price action and logic.
        """,
        "metaso_query": "分析 {name} ({code}) 近24小时内的最新重大利好利空消息、主力资金流向及当前市场情绪及近一个月的融资融券数据。请重点关注短线爆发点和潜在风险，忽略一周前的旧闻。",
        "metaso_query_fallback": "{name} ({code}) 最新研报",
        "metaso_parser": """
    你是一个客观信息提取器。
    
    【任务】
    仅提取 已核实的研报/新闻事件、具体数据点 或 官方公告。
    丢弃所有 观点、预测、“市场情绪”、“分析师展望” 或 “看涨/看跌” 等形容词。
    
    【已知事实 (数据库)】
    {existing_text}
    
    【新报告内容 (秘塔搜索结果)】
    {report_text}
    
    【要求】
    输出一个包含两个键的 JSON 对象：
    1. "new_claims": 字符串列表。
       - 必须是客观事实（例如：“公司发布 Q3 财报”，“股价触及 10.0”）。
       - 检查已知事实：如果已知事实已涵盖此事件/数据（语义相似），请丢弃，不要重复添加。
       - 严禁分析（例如：“股价看涨”，“分析师预期增长”）。
    2. "contradictions": 对象列表。如果新事实与已知事实冲突：
       {{
           "old_id": "ID", 
           "old_content": "旧内容...",
           "new_content": "新内容...",
           "judgement": "客观陈述冲突。"
       }}
    
    关键：执行严格的语义去重，不要添加冗余信息。仅输出纯 JSON。
    """
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
            
            # If it's a dict, merge with default
            if isinstance(data, dict):
                config = DEFAULT_CONFIG.copy()
                config.update(data)
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
    return db_get_position(code)

def update_position(code, shares, price, action="buy"):
    """
    Updates position based on action.
    action: 'buy' (calculate weighted avg), 'sell' (reduce shares), 'override' (overwrite)
    Synchronizes both SQLite DB and user_config.json.
    """
    # 1. Get current position (prefer DB as source of truth for runtime)
    current = db_get_position(code)
    
    curr_shares = current["shares"]
    curr_cost = current["cost"]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_shares = curr_shares
    new_cost = curr_cost

    if action == "buy":
        # Weighted Average
        total_value = (curr_shares * curr_cost) + (shares * price)
        new_shares = curr_shares + shares
        # Increase precision to 4 decimals to capture small changes
        new_cost = total_value / new_shares if new_shares > 0 else 0.0
        new_cost = round(new_cost, 4) 
        
        db_update_position(code, int(new_shares), new_cost)
        db_add_history(code, timestamp, "buy", price, shares, "手动买入")
        
    elif action == "sell":
        # Reducing shares does not change Avg Cost per share (Standard Accounting)
        new_shares = max(0, curr_shares - shares)
        # Cost remains same
        db_update_position(code, int(new_shares), curr_cost)
        db_add_history(code, timestamp, "sell", price, shares, "手动卖出")
        
    elif action == "override":
        # Direct clean update
        new_shares = int(shares)
        new_cost = round(price, 4)
        
        db_update_position(code, new_shares, new_cost)
        db_add_history(code, timestamp, "override", price, shares, "持仓修正")

    # 2. Sync to user_config.json to ensure consistency
    try:
        config = load_config()
        if "positions" not in config:
            config["positions"] = {}
        
        config["positions"][code] = {
            "shares": int(new_shares),
            "cost": float(new_cost)
        }
        
        # Ensure it's in selected_stocks if not already (auto-add)
        if "selected_stocks" not in config:
            config["selected_stocks"] = []
        if code not in config["selected_stocks"] and new_shares > 0:
             config["selected_stocks"].append(code)
             
        save_config(config)
    except Exception as e:
        print(f"Error syncing to user_config.json: {e}")

def delete_transaction(code: str, timestamp: str):
    """
    Deletes a transaction record by code and timestamp.
    """
    return db_delete_transaction(code, timestamp)

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
    Updates base_shares (Locked Position) in user_config.json
    """
    try:
        config = load_config()
        if "positions" not in config:
            config["positions"] = {}
        
        if code not in config["positions"]:
            config["positions"][code] = {"shares": 0, "cost": 0.0}
            
        config["positions"][code]["base_shares"] = int(shares)
        save_config(config)
        
        # Log it
        log_transaction(code, "base_position", price=0, volume=shares, note=f"Set Base Shares to {shares}")
    except Exception as e:
        print(f"Error setting base shares: {e}")
