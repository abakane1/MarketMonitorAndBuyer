# -*- coding: utf-8 -*-
"""
持仓限制检查
"""

from typing import Tuple


def check_position_limit(
    current_shares: int,
    trade_amount: int,
    action: str,
    max_position: int = 1000000
) -> Tuple[bool, str]:
    """
    检查持仓限制
    
    Args:
        current_shares: 当前持仓
        trade_amount: 交易数量
        action: 交易动作
        max_position: 最大持仓限制
        
    Returns:
        (是否允许, 消息)
    """
    action_str = str(action).lower()
    
    if action_str in ['sell', '卖出']:
        # 卖出检查
        if trade_amount > current_shares:
            return False, f"持仓不足: 当前{current_shares}股，卖出{trade_amount}股"
    
    elif action_str in ['buy', '买入']:
        # 买入检查
        new_shares = current_shares + trade_amount
        if new_shares > max_position:
            return False, f"超过最大持仓限制({max_position}股)"
    
    return True, "持仓检查通过"


def check_base_position_limit(
    shares: int,
    base_shares: int,
    new_base_shares: int
) -> Tuple[bool, str]:
    """
    检查底仓限制
    
    Args:
        shares: 当前持股数
        base_shares: 当前底仓数
        new_base_shares: 新的底仓数
        
    Returns:
        (是否允许, 消息)
    """
    if new_base_shares < 0:
        return False, "底仓不能为负"
    
    if new_base_shares > shares:
        return False, f"底仓({new_base_shares})不能超过持仓({shares})"
    
    return True, "底仓检查通过"
