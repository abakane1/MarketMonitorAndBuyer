# -*- coding: utf-8 -*-
"""
交易模拟器 (Trade Simulator)

v4.2.0 辅助模块
模拟真实交易环境，包括:
- 滑点模拟
- 手续费计算
- 市场冲击
- 部分成交

Author: AI Programmer
Date: 2026-03-14
"""

import random
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"          # 市价单
    LIMIT = "limit"            # 限价单
    STOP = "stop"              # 止损单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"        # 待成交
    FILLED = "filled"          # 已成交
    PARTIAL = "partial"        # 部分成交
    CANCELLED = "cancelled"    # 已取消
    REJECTED = "rejected"      # 已拒绝


@dataclass
class Order:
    """订单"""
    symbol: str
    action: str                # buy/sell
    order_type: OrderType
    shares: int
    price: Optional[float] = None  # 限价单价格
    status: OrderStatus = OrderStatus.PENDING
    filled_shares: int = 0
    filled_price: float = 0.0
    commission: float = 0.0


@dataclass
class SimulationConfig:
    """模拟配置"""
    slippage_mean: float = 0.001       # 滑点均值 (0.1%)
    slippage_std: float = 0.0005       # 滑点标准差
    commission_rate: float = 0.0003    # 手续费率
    min_commission: float = 5.0        # 最低手续费
    partial_fill_prob: float = 0.1     # 部分成交概率
    reject_prob: float = 0.01          # 拒单概率
    market_impact: float = 0.0001      # 市场冲击系数


class TradeSimulator:
    """
    交易模拟器
    
    模拟真实交易环境的各种因素
    """
    
    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
    
    def simulate_order(self, order: Order, market_price: float, 
                      market_volume: float = 0) -> Order:
        """
        模拟订单执行
        
        Args:
            order: 订单对象
            market_price: 市场价格
            market_volume: 市场成交量
            
        Returns:
            更新后的订单对象
        """
        # 1. 检查拒单
        if random.random() < self.config.reject_prob:
            order.status = OrderStatus.REJECTED
            return order
        
        # 2. 计算滑点
        slippage = self._calculate_slippage(order.action, market_volume)
        
        # 3. 计算成交价格
        if order.order_type == OrderType.MARKET:
            executed_price = self._apply_slippage(market_price, order.action, slippage)
        elif order.order_type == OrderType.LIMIT:
            # 限价单检查
            if order.action == 'buy' and market_price > order.price:
                order.status = OrderStatus.PENDING
                return order
            elif order.action == 'sell' and market_price < order.price:
                order.status = OrderStatus.PENDING
                return order
            executed_price = order.price
        else:
            executed_price = market_price
        
        # 4. 检查部分成交
        fill_ratio = self._calculate_fill_ratio(market_volume)
        filled_shares = int(order.shares * fill_ratio)
        
        if filled_shares == 0:
            order.status = OrderStatus.PENDING
            return order
        
        if filled_shares < order.shares:
            order.status = OrderStatus.PARTIAL
        else:
            order.status = OrderStatus.FILLED
        
        # 5. 计算手续费
        commission = self._calculate_commission(executed_price, filled_shares)
        
        # 更新订单
        order.filled_shares = filled_shares
        order.filled_price = executed_price
        order.commission = commission
        
        return order
    
    def _calculate_slippage(self, action: str, market_volume: float) -> float:
        """计算滑点"""
        # 基础滑点
        base_slippage = random.gauss(
            self.config.slippage_mean,
            self.config.slippage_std
        )
        
        # 市场冲击 (成交量越大，冲击越小)
        if market_volume > 0:
            impact = self.config.market_impact / (market_volume ** 0.5)
            base_slippage += impact
        
        return max(base_slippage, 0)
    
    def _apply_slippage(self, price: float, action: str, slippage: float) -> float:
        """应用滑点到价格"""
        if action == 'buy':
            # 买入时价格上涨
            return price * (1 + slippage)
        else:  # sell
            # 卖出时价格下跌
            return price * (1 - slippage)
    
    def _calculate_fill_ratio(self, market_volume: float) -> float:
        """计算成交比例"""
        # 基础成交概率
        base_fill = 1.0
        
        # 部分成交概率
        if random.random() < self.config.partial_fill_prob:
            # 随机成交50-95%
            base_fill = random.uniform(0.5, 0.95)
        
        return base_fill
    
    def _calculate_commission(self, price: float, shares: int) -> float:
        """计算手续费"""
        trade_value = price * shares
        commission = trade_value * self.config.commission_rate
        return max(commission, self.config.min_commission)
    
    def simulate_market_impact(self, order_size: int, 
                               average_daily_volume: float) -> float:
        """
        计算市场冲击成本
        
        Args:
            order_size: 订单规模
            average_daily_volume: 日均成交量
            
        Returns:
            冲击成本 (价格变动百分比)
        """
        if average_daily_volume == 0:
            return 0.0
        
        # 参与率
        participation_rate = order_size / average_daily_volume
        
        # 平方根模型
        impact = self.config.market_impact * (participation_rate ** 0.5)
        
        return impact


class MarketSimulator:
    """
    市场模拟器
    
    模拟市场环境，包括:
    - 价格波动
    - 成交量变化
    - 流动性变化
    """
    
    def __init__(self):
        self.price_history = []
        self.volume_history = []
    
    def simulate_price_move(self, current_price: float, 
                           volatility: float = 0.02) -> float:
        """
        模拟价格变动
        
        Args:
            current_price: 当前价格
            volatility: 波动率
            
        Returns:
            新价格
        """
        # 随机漫步
        change = random.gauss(0, volatility)
        new_price = current_price * (1 + change)
        return max(new_price, 0.01)  # 确保价格大于0
    
    def simulate_volume(self, average_volume: float) -> float:
        """
        模拟成交量
        
        Args:
            average_volume: 平均成交量
            
        Returns:
            模拟成交量
        """
        # 成交量服从对数正态分布
        log_volume = random.gauss(
            np.log(average_volume),
            0.5  # 标准差
        )
        return np.exp(log_volume)


# 便捷函数
def quick_simulate_trade(action: str, price: float, shares: int,
                        config: Optional[SimulationConfig] = None) -> Dict:
    """
    快速模拟单笔交易
    
    Args:
        action: buy/sell
        price: 价格
        shares: 数量
        config: 模拟配置
        
    Returns:
        交易结果
    """
    simulator = TradeSimulator(config)
    
    order = Order(
        symbol="TEST",
        action=action,
        order_type=OrderType.MARKET,
        shares=shares
    )
    
    result = simulator.simulate_order(order, price)
    
    return {
        'action': result.action,
        'requested_shares': shares,
        'filled_shares': result.filled_shares,
        'filled_price': result.filled_price,
        'commission': result.commission,
        'status': result.status.value,
        'slippage': abs(result.filled_price - price) / price
    }


if __name__ == "__main__":
    # 测试交易模拟器
    print("🧪 测试交易模拟器")
    print("=" * 50)
    
    import numpy as np
    
    # 配置
    config = SimulationConfig(
        slippage_mean=0.001,
        commission_rate=0.0003,
        partial_fill_prob=0.2
    )
    
    simulator = TradeSimulator(config)
    
    # 测试买入
    print("\n测试买入 1000股 @ ¥10.00:")
    for i in range(5):
        result = quick_simulate_trade('buy', 10.0, 1000, config)
        print(f"  成交: {result['filled_shares']}股 @ ¥{result['filled_price']:.4f}, "
              f"手续费: ¥{result['commission']:.2f}, "
              f"滑点: {result['slippage']:.4%}")
    
    # 测试卖出
    print("\n测试卖出 1000股 @ ¥11.00:")
    for i in range(5):
        result = quick_simulate_trade('sell', 11.0, 1000, config)
        print(f"  成交: {result['filled_shares']}股 @ ¥{result['filled_price']:.4f}, "
              f"手续费: ¥{result['commission']:.2f}, "
              f"滑点: {result['slippage']:.4%}")
