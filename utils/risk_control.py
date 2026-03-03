import logging
import json
import os
from datetime import datetime
from typing import Tuple, Dict

from utils.database import db_get_position, db_compute_realized_pnl, get_db_connection

logger = logging.getLogger(__name__)

# 默认风控配置
DEFAULT_RISK_CONFIG = {
    "max_position_pct": 0.30,  # 单只标仓位限额 30%
    "max_daily_loss_pct": 0.10,  # 单只标的单日最大亏损限额 10%
    "max_total_loss_pct": 0.05,  # 账户整体最大回撤限额 5% (暂保留)
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_config.json")

def get_total_capital() -> float:
    """获取总资金池"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return float(config.get("settings", {}).get("total_capital", 100000.0))
    except Exception as e:
        logger.error(f"读取 user_config.json 失败: {e}")
    return 100000.0

def get_risk_config() -> Dict:
    """获取风控参数配置（可从本地 JSON 加载覆盖默认）"""
    return DEFAULT_RISK_CONFIG

def check_pre_trade_risk(symbol: str, action: str, shares: int, price: float) -> Tuple[bool, str]:
    """
    事前检查逻辑（策略生成后、执行前）
    检查仓位限额是否超标。
    返回 (是否通过, 提示信息)
    """
    if str(action).lower() not in ['buy', '买入', '快速买入']:
        return True, "非买入操作，免风险校验"
        
    config = get_risk_config()
    total_capital = get_total_capital()
    
    trade_value = shares * price
    max_allow = total_capital * config["max_position_pct"]
    
    current_pos = db_get_position(symbol)
    current_shares = int(current_pos.get('shares', 0))
    current_value = current_shares * price
    
    post_value = current_value + trade_value
    
    if post_value > max_allow:
        reason = f"【风控触发】{symbol} 目标持仓市值(￥{post_value:,.2f}) 将超过单品限额(￥{max_allow:,.2f}, {config['max_position_pct']*100}%)"
        logger.warning(reason)
        return False, reason
        
    return True, "风控检查通过"

def get_stepped_stop_loss_price(cost_price: float, current_price: float, highest_price: float = None) -> float:
    """
    阶梯止损/止盈价格计算
    1. 默认底线止损：成本价向下 5% 或 8% (可配)。
    2. 若已有一定盈利 (如 10%)，则止损线提高至成本价。
    3. 若处于高盈利区间，采用移动止损 (如最高价回撤 5%)。
    返回建议的止损触发价。
    """
    if cost_price <= 0:
        return 0.0
        
    # 第一阶梯：基础硬止损 (跌破成本的 8%)
    stop_loss_price = cost_price * 0.92
    
    # 模拟更高阶梯逻辑 (需要结合历史最高价，此处作演示简化)
    if highest_price and highest_price > cost_price * 1.15: # 浮盈 > 15%
        # 移动止盈：从最高点回撤 8%
        trailing_stop = highest_price * 0.92
        stop_loss_price = max(stop_loss_price, trailing_stop)
        
    elif current_price > cost_price * 1.10: # 浮盈 > 10%
        # 保本止盈 (保底 2% 利润抵扣手续费)
        profit_protection = cost_price * 1.02
        stop_loss_price = max(stop_loss_price, profit_protection)
        
    return round(stop_loss_price, 3)

def check_daily_loss_limit(symbol: str) -> Tuple[bool, str]:
    """
    单日亏损限额检查 (检查某只股票今天的流水是否已亏损超10%)
    """
    pnl_data = db_compute_realized_pnl(symbol)
    daily_list = pnl_data.get("daily_pnl", [])
    today = datetime.now().strftime("%Y-%m-%d")
    
    today_pnl = 0.0
    for d in daily_list:
        if d["date"] == today:
            today_pnl = d["pnl"]
            break
            
    if today_pnl < 0:
        config = get_risk_config()
        total_capital = get_total_capital()
        max_daily_loss = total_capital * config["max_daily_loss_pct"]
        
        if abs(today_pnl) > max_daily_loss:
            return False, f"【风控触发】{symbol} 今日已亏损 ￥{abs(today_pnl):,.2f}，超过单日限额 ￥{max_daily_loss:,.2f}"
            
    return True, "单日亏损检查通过"
