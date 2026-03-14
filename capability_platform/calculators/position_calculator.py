# -*- coding: utf-8 -*-
"""
持仓计算器

统一的持仓计算逻辑，单一事实来源。
"""

from typing import List, Tuple
from data_platform.models.trade import TradeModel, TradeAction


class PositionCalculator:
    """
    持仓计算器
    
    所有持仓计算的统一入口。
    
    算法说明：
    1. 买入：加权平均成本法
       new_cost = (current_shares * current_cost + trade_amount * trade_price) / new_shares
    
    2. 卖出：摊薄成本法
       new_cost = (current_total_cost - sell_revenue) / new_shares
       其中 sell_revenue = trade_amount * trade_price
    
    3. 修正：直接覆盖
       new_shares = trade_amount
       new_cost = trade_price
    """
    
    @staticmethod
    def calculate_new_position(
        current_shares: int,
        current_cost: float,
        action: TradeAction,
        trade_price: float,
        trade_amount: int
    ) -> Tuple[int, float]:
        """
        计算新的持仓状态
        
        Args:
            current_shares: 当前持股数量
            current_cost: 当前成本价
            action: 交易动作
            trade_price: 成交价格
            trade_amount: 成交数量
            
        Returns:
            (new_shares, new_cost)
        """
        if action == TradeAction.BUY:
            return PositionCalculator._calc_buy(
                current_shares, current_cost, trade_price, trade_amount
            )
        elif action == TradeAction.SELL:
            return PositionCalculator._calc_sell(
                current_shares, current_cost, trade_price, trade_amount
            )
        elif action == TradeAction.OVERRIDE:
            return PositionCalculator._calc_override(
                trade_price, trade_amount
            )
        else:
            # 不影响持仓的操作
            return current_shares, current_cost
    
    @staticmethod
    def _calc_buy(
        current_shares: int,
        current_cost: float,
        trade_price: float,
        trade_amount: int
    ) -> Tuple[int, float]:
        """
        买入计算 - 加权平均成本法
        """
        new_shares = current_shares + trade_amount
        
        if new_shares <= 0:
            return 0, 0.0
        
        current_total_cost = current_shares * current_cost
        trade_total_cost = trade_amount * trade_price
        new_cost = (current_total_cost + trade_total_cost) / new_shares
        
        return new_shares, round(new_cost, 4)
    
    @staticmethod
    def _calc_sell(
        current_shares: int,
        current_cost: float,
        trade_price: float,
        trade_amount: int
    ) -> Tuple[int, float]:
        """
        卖出计算 - 摊薄成本法
        
        算法：卖出后减少的成本 = 卖出金额
        这是用户要求的"卖出降成本"逻辑
        """
        new_shares = current_shares - trade_amount
        
        if new_shares <= 0:
            return 0, 0.0
        
        current_total_cost = current_shares * current_cost
        sell_revenue = trade_amount * trade_price
        new_total_cost = current_total_cost - sell_revenue
        new_cost = new_total_cost / new_shares
        
        return new_shares, round(new_cost, 4)
    
    @staticmethod
    def _calc_override(
        trade_price: float,
        trade_amount: int
    ) -> Tuple[int, float]:
        """
        持仓修正 - 直接覆盖
        """
        return trade_amount, round(trade_price, 4)
    
    @staticmethod
    def recalculate_from_trades(
        trades: List[TradeModel],
        initial_shares: int = 0,
        initial_cost: float = 0.0
    ) -> Tuple[int, float, int]:
        """
        从交易历史重新计算持仓
        
        这是解决数据不一致的核心算法。
        
        Args:
            trades: 交易历史列表（按时间排序）
            initial_shares: 初始持股
            initial_cost: 初始成本
            
        Returns:
            (shares, cost, base_shares)
        """
        shares = initial_shares
        cost = initial_cost
        base_shares = 0
        
        for trade in trades:
            if trade.action == TradeAction.BASE_POSITION:
                base_shares = trade.amount
                continue
            
            if not trade.action.affects_position():
                continue
            
            shares, cost = PositionCalculator.calculate_new_position(
                current_shares=shares,
                current_cost=cost,
                action=trade.action,
                trade_price=trade.price,
                trade_amount=trade.amount
            )
        
        return shares, cost, base_shares
    
    @staticmethod
    def calculate_avg_cost(shares: int, total_cost: float) -> float:
        """计算平均成本"""
        if shares <= 0:
            return 0.0
        return round(total_cost / shares, 4)
