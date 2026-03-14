# -*- coding: utf-8 -*-
"""
费率计算器

统一的费率计算逻辑。
"""

from typing import Dict
from utils.asset_classifier import is_etf


class FeeCalculator:
    """
    费率计算器
    
    所有费率计算的统一入口。
    
    ETF费率规则：
    - 佣金：万1（最低5元）
    - 印花税：免
    - 过户费：免
    
    股票费率规则：
    - 佣金：万3（最低5元）
    - 印花税：万5（卖出时收取）
    - 过户费：万0.1（双向）
    """
    
    # ETF费率
    ETF_COMMISSION_RATE = 0.0001  # 万1
    ETF_MIN_FEE = 5.0
    
    # 股票费率
    STOCK_COMMISSION_RATE = 0.0003  # 万3
    STOCK_MIN_FEE = 5.0
    STOCK_STAMP_DUTY_RATE = 0.0005  # 万5（卖出）
    STOCK_TRANSFER_FEE_RATE = 0.00001  # 万0.1
    
    @classmethod
    def calculate(
        cls,
        symbol: str,
        price: float,
        amount: int,
        is_sell: bool
    ) -> Dict[str, float]:
        """
        计算交易费用
        
        Args:
            symbol: 股票代码
            price: 成交价格
            amount: 成交数量
            is_sell: 是否卖出
            
        Returns:
            {
                'fee': 佣金,
                'stamp_duty': 印花税,
                'transfer_fee': 过户费,
                'total': 总费用
            }
        """
        trade_value = price * amount
        
        if is_etf(symbol):
            return cls._calc_etf_fee(trade_value, is_sell)
        else:
            return cls._calc_stock_fee(trade_value, is_sell)
    
    @classmethod
    def _calc_etf_fee(cls, trade_value: float, is_sell: bool) -> Dict[str, float]:
        """计算ETF费用"""
        fee = max(cls.ETF_MIN_FEE, round(trade_value * cls.ETF_COMMISSION_RATE, 2))
        
        return {
            'fee': fee,
            'stamp_duty': 0.0,
            'transfer_fee': 0.0,
            'total': fee
        }
    
    @classmethod
    def _calc_stock_fee(cls, trade_value: float, is_sell: bool) -> Dict[str, float]:
        """计算股票费用"""
        # 佣金
        fee = max(cls.STOCK_MIN_FEE, round(trade_value * cls.STOCK_COMMISSION_RATE, 2))
        
        # 印花税（仅卖出）
        stamp_duty = round(trade_value * cls.STOCK_STAMP_DUTY_RATE, 2) if is_sell else 0.0
        
        # 过户费
        transfer_fee = round(trade_value * cls.STOCK_TRANSFER_FEE_RATE, 2)
        
        return {
            'fee': fee,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'total': fee + stamp_duty + transfer_fee
        }
    
    @classmethod
    def calculate_buy_fee(cls, symbol: str, price: float, amount: int) -> float:
        """计算买入费用"""
        fees = cls.calculate(symbol, price, amount, is_sell=False)
        return fees['total']
    
    @classmethod
    def calculate_sell_fee(cls, symbol: str, price: float, amount: int) -> float:
        """计算卖出费用"""
        fees = cls.calculate(symbol, price, amount, is_sell=True)
        return fees['total']
    
    @classmethod
    def calculate_net_proceeds(
        cls,
        symbol: str,
        buy_price: float,
        sell_price: float,
        amount: int
    ) -> Dict[str, float]:
        """
        计算净收益
        
        Returns:
            {
                'gross_profit': 毛利润,
                'buy_fee': 买入费用,
                'sell_fee': 卖出费用,
                'total_fee': 总费用,
                'net_profit': 净利润
            }
        """
        buy_fee = cls.calculate_buy_fee(symbol, buy_price, amount)
        sell_fee = cls.calculate_sell_fee(symbol, sell_price, amount)
        
        gross_profit = (sell_price - buy_price) * amount
        total_fee = buy_fee + sell_fee
        net_profit = gross_profit - total_fee
        
        return {
            'gross_profit': round(gross_profit, 2),
            'buy_fee': buy_fee,
            'sell_fee': sell_fee,
            'total_fee': total_fee,
            'net_profit': round(net_profit, 2)
        }
