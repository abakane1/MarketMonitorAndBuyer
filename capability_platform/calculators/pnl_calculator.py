# -*- coding: utf-8 -*-
"""
盈亏计算器

统一的盈亏计算逻辑。
"""

from typing import List, Dict
from data_platform.models.trade import TradeModel, TradeAction


class PnLCalculator:
    """
    盈亏计算器
    
    所有盈亏计算的统一入口。
    
    计算类型：
    1. 浮动盈亏：当前市值 - 成本
    2. 今日盈亏：(现价 - 昨收) * 持股数
    3. 已实现盈亏：使用移动平均成本法
    """
    
    # ========== 基础计算 ==========
    
    @staticmethod
    def calculate_floating_pnl(shares: int, cost: float, current_price: float) -> float:
        """
        计算浮动盈亏
        
        Formula: (current_price - cost) * shares
        """
        if shares <= 0:
            return 0.0
        return shares * (current_price - cost)
    
    @staticmethod
    def calculate_floating_pnl_pct(cost: float, current_price: float) -> float:
        """
        计算浮动盈亏百分比
        
        Formula: (current_price - cost) / cost * 100
        """
        if cost <= 0:
            return 0.0
        return (current_price - cost) / cost * 100
    
    @staticmethod
    def calculate_today_pnl(shares: int, current_price: float, pre_close: float) -> float:
        """
        计算今日盈亏
        
        Formula: (current_price - pre_close) * shares
        """
        if shares <= 0 or pre_close <= 0:
            return 0.0
        return shares * (current_price - pre_close)
    
    @staticmethod
    def calculate_today_pnl_pct(current_price: float, pre_close: float) -> float:
        """
        计算今日涨跌幅
        
        Formula: (current_price - pre_close) / pre_close * 100
        """
        if pre_close <= 0:
            return 0.0
        return (current_price - pre_close) / pre_close * 100
    
    # ========== 已实现盈亏计算 ==========
    
    @staticmethod
    def calculate_realized_pnl(trades: List[TradeModel]) -> Dict:
        """
        使用移动平均成本法计算已实现盈亏
        
        Args:
            trades: 按时间排序的交易列表
            
        Returns:
            {
                'realized_pnl': 累计已实现盈亏,
                'total_buy_amount': 累计买入金额,
                'total_sell_amount': 累计卖出金额,
                'trade_count': 交易次数,
                'daily_pnl': 每日盈亏列表
            }
        """
        shares = 0
        total_cost = 0.0
        realized_pnl = 0.0
        total_buy_amount = 0.0
        total_sell_amount = 0.0
        trade_count = 0
        
        # 按日聚合
        daily_pnl_map = {}
        
        for trade in trades:
            if trade.amount <= 0 or trade.price <= 0:
                continue
            
            trade_count += 1
            date_str = trade.timestamp.strftime('%Y-%m-%d')
            
            # 持仓修正
            if trade.is_override():
                shares = trade.amount
                total_cost = trade.amount * trade.price
                continue
            
            if trade.is_buy():
                # 买入：增加持仓
                shares += trade.amount
                total_cost += trade.amount * trade.price
                total_buy_amount += trade.amount * trade.price
                
            elif trade.is_sell():
                # 卖出：计算已实现盈亏
                if shares > 0:
                    avg_cost = total_cost / shares
                    # 本次卖出的已实现盈亏
                    pnl = (trade.price - avg_cost) * trade.amount
                    realized_pnl += pnl
                    total_sell_amount += trade.amount * trade.price
                    
                    # 记录日盈亏
                    if date_str not in daily_pnl_map:
                        daily_pnl_map[date_str] = 0.0
                    daily_pnl_map[date_str] += pnl
                    
                    # 减少持仓
                    shares -= trade.amount
                    if shares <= 0:
                        shares = 0
                        total_cost = 0.0
                    else:
                        total_cost = shares * avg_cost
        
        # 转换为列表
        daily_pnl = []
        cum_pnl = 0.0
        for date in sorted(daily_pnl_map.keys()):
            cum_pnl += daily_pnl_map[date]
            daily_pnl.append({
                'date': date,
                'pnl': round(daily_pnl_map[date], 2),
                'cumulative_pnl': round(cum_pnl, 2)
            })
        
        return {
            'realized_pnl': round(realized_pnl, 2),
            'total_buy_amount': round(total_buy_amount, 2),
            'total_sell_amount': round(total_sell_amount, 2),
            'trade_count': trade_count,
            'daily_pnl': daily_pnl
        }
    
    # ========== 组合盈亏计算 ==========
    
    @staticmethod
    def calculate_portfolio_metrics(
        positions: List[dict],
        quotes: dict
    ) -> Dict:
        """
        计算组合整体指标
        
        Args:
            positions: 持仓列表，每项包含 {'symbol', 'shares', 'cost'}
            quotes: 行情字典，key=symbol, value=quote
            
        Returns:
            {
                'total_market_value': 总市值,
                'total_cost_value': 总成本,
                'total_floating_pnl': 总浮动盈亏,
                'total_today_pnl': 总今日盈亏,
            }
        """
        total_market_value = 0.0
        total_cost_value = 0.0
        total_floating_pnl = 0.0
        total_today_pnl = 0.0
        
        for pos in positions:
            symbol = pos['symbol']
            shares = pos['shares']
            cost = pos['cost']
            
            quote = quotes.get(symbol)
            if not quote:
                continue
            
            market_value = shares * quote.price
            cost_value = shares * cost
            floating_pnl = shares * (quote.price - cost)
            today_pnl = shares * (quote.price - quote.pre_close)
            
            total_market_value += market_value
            total_cost_value += cost_value
            total_floating_pnl += floating_pnl
            total_today_pnl += today_pnl
        
        return {
            'total_market_value': round(total_market_value, 2),
            'total_cost_value': round(total_cost_value, 2),
            'total_floating_pnl': round(total_floating_pnl, 2),
            'total_today_pnl': round(total_today_pnl, 2),
            'floating_pnl_pct': round(
                (total_floating_pnl / total_cost_value * 100), 2
            ) if total_cost_value > 0 else 0.0
        }
