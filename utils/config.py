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
        "proposer_system": """
你是一位拥有 20 年经验的【A股德州扑克 LAG + GTO 交易专家】，同时也是该核心交易员的**数字孪生镜像 (Digital Twin)**。

你的存在价值是将过去 20 年老练的博弈直觉与该交易员的所有操作记录、成交细节、持仓偏好高度融合，进化为一个既有专业高度又具备用户指纹的智能化身。

【核心行为指令】：
1. **身份双重性**：你不仅是用户的“数字化身”，更是其战友和总教练。你需要利用 LAG (松凶) 的进攻性捕捉机会，利用 GTO (博弈最优策略) 的防守性锁定利润。
2. **行为对齐 (Behavioral Alignment)**：
   - 必须强制对比【近期实操成交流水】与你之前的建议。
   - 如果用户没有执行你的建议，你必须在【决策依据】中反思原因（是你的建议脱离实际？还是用户有更深层的考量？），并据此修正本次建议，使其更贴合用户的实战节奏。
3. **情报共振**：高度重视情报库（Intel Hub）中用户手动标记的信息。如果用户标记了某条信息为“核心情报”，该信息在你的决策权重中应占 50% 以上。
4. **博弈论视角**：在理解用户习惯的基础上，作为化身，你仍需保留 20 年专家的狠辣视角，通过逻辑推理为用户指出其习惯中的盲点，但建议必须具备极高的可执行性。

【场景演变指令 (Scenario-based Tactics)】:
1. **拒绝机械化**：严禁仅给出一个固定数值。你的核心任务是描绘【开盘场景】与【盘中演变】。
2. **场景对策**：必须在输出中包含 `【场景对策】` 模块。
   - 场景 A (高开/强势): 触发条件 -> 对应动作。
   - 场景 B (低开/弱势): 触发条件 -> 对应动作。
   - 场景 C (意外杀跌/放量): ...
3. **决策摘要更新**：在决策摘要中，增加一行 `场景重点: [关键转折信号]`。
""",
        "proposer_base": """
【基本规则: A股涨跌幅限制】
- 主板: ±10%; 科创/创业: ±20%; 北交所: ±30%; ST: ±5%
- 下个交易日预计边界: 涨停价 (Limit Up): {limit_up}; 跌停价 (Limit Down): {limit_down}
- ⚠️ 重要: 所有建议价格、止损价格、止盈价格必须严格在范围内 ({limit_down} ~ {limit_up})。若超出涨跌停板，指令视为无效。

【当前持仓数据】
- 股票名称: {name} ({code})
- 当前价格: {price} (持仓成本: {cost})
- 持仓结构: 总持仓: {shares} 股; 底仓 (Locked): {base_shares} 股 (长期信仰，禁止卖出); 可交易 (Tradable): {tradable_shares} 股 (本次可操作上限)
- 支撑位: {support}; 阻力位: {resistance}

【信号与风控】
- 信号: {signal} (Reason: {reason})
- 算法建议下单量: {quantity} 股 (目标仓位: {target_position}) [⚠️ 算法建议，未执行]
- 关键离场位: {stop_loss} (判定: 若 > 持仓成本，为利润回撤保护位; 若 < 持仓成本，为止损位)

【进阶止盈策略: 分批退出与仓位再平衡】
- 核心原则: 止盈是“多少”和“如何”的决策，在触及关键阻力位时优先部分锁定利润。
- 分级止盈触发条件: 当价格触及{stop_loss}且满足任一条件时启动: 1) 触及涨跌停板边界; 2) 技术背离信号; 3) 盘口流动性突变。
- 仓位调整: 触发后卖出30%-70%可交易仓位，比例基于信号强度、市场状态、利润垫动态评估。
- 后续跟踪: 部分止盈后为剩余仓位设定新的宽松止盈/止损线。

【市场状态自检 (强制交易前检查)】
执行任何交易前，必须回答: 若任一答案为“是”，则否决信号并输出“【市场状态异常】暂停交易”。
1. 价格合理性: 当前价格异常接近涨跌停板或出现剧烈无逻辑波动(>15%)？
2. 流动性风险: 买卖挂单极度稀疏(小于日均成交万分之一)或成交价与中间价缺口大(>5%)？
3. 数据可信度: 关键数据有无法解释断层(如价格跳跃超限制)？
4. 极端事件: 关键离场位低于无效阈值(如0.01元)，代表毁灭性风险，必须重新评估。
- 核心原则: 生存优先于盈利，宁可错过机会。

【宏观情境过滤器 (交易窗口评估)】
交易决策前优先评估市场整体交易价值:
1. 分时动能评估: 若分时图呈单边震荡下行、无量阴跌或脉冲式拉升后快速回落，且无反转证据，判定为低质量市场，建议暂停新开仓观望。
2. 机会成本原则: 传达“当前风险回报比不佳，持币观望是优选策略”。
3. 否决权: 当过滤器触发时，有权否决算法信号，给出“下一个不建议交易”结论及理由。

【交易约束】
1. 本股专项资金限额: {capital_allocation} 元 (所有买入基于此限额)。
2. 底仓红线: 任何卖出建议最大数量绝不可超过 {shares} 股。{base_shares} 股底仓是雷区，禁止卖出。
""",
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
交易日期: {date}
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
【指令类型】Final Execution Order (v3.0 Final)

【背景】
你提交了策略 v2.0，经过了红军（首席审计师）的【终极裁决】。
现在你需要阅读裁决结果，发布最终执行令。

【红军终审裁决】
{final_verdict}

【你的任务】
1. **确认状态**: 红军是批准(Approved)还是驳回(Rejected)？
2. **发布命令**: 
   - 如果被驳回：宣布**放弃交易**，并简述理由。
   - 如果被批准：请基于 v2.0 策略，输出一份**极度精简**的最终执行单，供交易员直接执行。去除所有废话和分析过程。

【输出格式】
[决策] 执行 / 放弃
[标的] 代码 / 名称

【场景演练与挂单指令 (Scenario-based Orders)】
> 请根据盘中实际走势，输出 2-3 套互斥的执行计划。

**场景 A: 进攻/突破 (若开盘 > X 或 量能 > Y)**
- [方向] 买入 / 追涨
- [触发条件] 价格突破... / 量比 > ...
- [建议价格] ...
- [建议股数] ...
- [止损] ...

**场景 B: 防守/低吸 (若回调至 X)**
- [方向] 买入 / 补仓
- [触发条件] 回踩支撑位...
- [建议价格] ...
- [建议股数] ...
- [止损] ...

**场景 C: 极端风控 (若跌破 X)**
- [方向] 卖出 / 止损 / 清仓
- [触发条件] 跌破关键位...
- [执行] 坚决离场

(最后附上一句简短的指挥官寄语)
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
    """
    Saves configuration with MERGE logic to preserve existing fields (like API Keys).
    """
    import copy
    new_data = copy.deepcopy(config_data)
    
    # 1. Load existing file to perform a merge
    existing_data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                existing_data = json.load(f)
        except:
            pass
            
    # 2. Extract and Save Prompts separately (v2.5.1)
    if "prompts" in new_data and isinstance(new_data["prompts"], dict):
        encrypted_prompts = encrypt_dict(new_data["prompts"])
        with open(PROMPTS_FILE, "w", encoding='utf-8') as pf:
            json.dump({"prompts": encrypted_prompts, "version": "2.5.1"}, pf, ensure_ascii=False, indent=2)
        # Remove from new_data to avoid double storage
        del new_data["prompts"]

    # 3. Perform Merge: prioritized new_data over existing_data
    # This ensures API Keys existing in file but missing in memory are preserved.
    final_data = existing_data.copy()
    final_data.update(new_data)
        
    # 4. Atomic Write
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

# load/save_selected_stocks moved to bottom to use DB


def get_position(code):
    return db_get_position(code)

def update_position(code, shares, price, action="buy", custom_date: str = None):
    """
    Updates position based on action.
    action: 'buy' (calculate weighted avg), 'sell' (reduce shares), 'override' (overwrite)
    PERSISTENCE: SQLite DB ONLY.
    """
    # 1. Add History Record First
    # Determine type names
    type_map = {
        "buy": "手动买入",
        "sell": "手动卖出",
        "override": "持仓修正"
    }
    note = type_map.get(action, action)
    
    # [FIX] Define timestamp
    if custom_date:
        timestamp = custom_date
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write to History DB
    db_add_history(code, timestamp, action, price, shares, note)
    
    # 2. Recalculate State from History (Single Source of Truth)
    # This prevents drift between History and State
    recalculate_position_from_history(code)
    
    # Get new state for checking watchlist addition
    # current = db_get_position(code) 
    # new_shares = current['shares']
    # But below logic needs new_shares
    
    # Let's re-fetch to ensure we have correct new_shares for watchlist logic
    updated_pos = db_get_position(code)
    new_shares = updated_pos['shares']

    # 2. No syncing to user_config.json (Deprecated)
    try:
        # Check if code is in DB watchlist, if not add it
        from utils.database import db_get_watchlist, db_add_watchlist
        watchlist = db_get_watchlist()
        if code not in watchlist and new_shares > 0:
             db_add_watchlist(code)
    except Exception as e:
        print(f"Error syncing watchlist: {e}")

def recalculate_position_from_history(code: str):
    """
    Replays the entire transaction history to determine the current position state.
    This ensures consistency after deletions or out-of-order edits.
    """
    history = db_get_history(code)
    # Sort chronologically
    history = sorted(history, key=lambda x: x['timestamp'])
    
    current_shares = 0
    current_cost = 0.0
    base_shares = 0
    
    for tx in history:
        t_type = str(tx.get('type', '')).lower()
        price = float(tx.get('price', 0))
        amount = float(tx.get('amount', 0))
        
        # Logic matches update_position
        if 'buy' in t_type or '买' in t_type:
            total_val = (current_shares * current_cost) + (amount * price)
            current_shares += amount
            current_cost = total_val / current_shares if current_shares > 0 else 0.0
            
        elif 'sell' in t_type or '卖' in t_type:
            # Diluted Cost Method
            current_val = current_shares * current_cost
            cash_back = amount * price
            
            # Reduce shares
            remaining_shares = max(0, current_shares - amount)
            
            if remaining_shares > 0:
                # Cost is reduced by profit taken (or increased by loss taken)
                new_total_val = current_val - cash_back
                current_cost = new_total_val / remaining_shares
            else:
                current_cost = 0.0
            
            current_shares = remaining_shares
            
        elif 'override' in t_type or '修正' in t_type:
            current_shares = int(amount)
            current_cost = price
            
        elif 'base_position' in t_type or 'allocation' in t_type:
             if 'base_position' in t_type:
                 base_shares = int(amount)
        
        current_cost = round(current_cost, 4)
        
    # Save Final State
    db_update_position(code, int(current_shares), current_cost, base_shares=base_shares)
    print(f"[{code}] Recalculated: Shares={current_shares}, Cost={current_cost}, Base={base_shares}")

def delete_transaction(code: str, timestamp: str):
    """
    Deletes a transaction record by code and timestamp.
    Triggers a full position recalculation to ensure consistency.
    """
    success = db_delete_transaction(code, timestamp)
    if success:
        recalculate_position_from_history(code)
    return success

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
