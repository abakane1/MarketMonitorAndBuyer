# -*- coding: utf-8 -*-
"""
持仓数据模型

持仓的唯一事实来源，所有持仓相关数据都通过此模型处理。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .base import BaseModel, AssetType


@dataclass(frozen=True)
class PositionModel(BaseModel):
    """
    持仓模型
    
    Attributes:
        symbol: 股票代码
        shares: 当前持股数量
        cost: 成本价（加权平均）
        base_shares: 底仓数量
        asset_type: 资产类型（自动推断）
    """
    
    symbol: str = ''
    shares: int = 0
    cost: float = 0.0
    base_shares: int = 0
    asset_type: AssetType = field(default=None)
    
    def __post_init__(self):
        # 自动推断资产类型
        if self.asset_type is None:
            object.__setattr__(
                self, 
                'asset_type', 
                AssetType.from_symbol(self.symbol)
            )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'shares': self.shares,
            'cost': self.cost,
            'base_shares': self.base_shares,
            'asset_type': self.asset_type.value,
            'updated_at': self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionModel":
        return cls(
            symbol=data['symbol'],
            shares=int(data.get('shares', 0)),
            cost=float(data.get('cost', 0.0)),
            base_shares=int(data.get('base_shares', 0)),
            asset_type=AssetType(data.get('asset_type', 'stock')),
        )
    
    def validate(self) -> tuple[bool, str]:
        """数据校验"""
        if not self.symbol or len(self.symbol) < 6:
            return False, f"无效的股票代码: {self.symbol}"
        
        if self.shares < 0:
            return False, f"持股数量不能为负: {self.shares}"
        
        if self.cost < 0:
            return False, f"成本价不能为负: {self.cost}"
        
        if self.base_shares < 0:
            return False, f"底仓数量不能为负: {self.base_shares}"
        
        if self.base_shares > self.shares:
            return False, f"底仓({self.base_shares})不能超过持仓({self.shares})"
        
        return True, ""
    
    # ========== 计算属性 ==========
    
    def market_value(self, current_price: float) -> float:
        """当前市值"""
        return self.shares * current_price
    
    def floating_pnl(self, current_price: float) -> float:
        """浮动盈亏 = (现价 - 成本) * 持股数"""
        return self.shares * (current_price - self.cost)
    
    def floating_pnl_pct(self, current_price: float) -> float:
        """浮动盈亏百分比"""
        if self.cost <= 0:
            return 0.0
        return (current_price - self.cost) / self.cost * 100
    
    def today_pnl(self, current_price: float, pre_close: float) -> float:
        """今日盈亏 = (现价 - 昨收) * 持股数"""
        return self.shares * (current_price - pre_close)
    
    def total_cost_value(self) -> float:
        """总成本 = 持股数 * 成本价"""
        return self.shares * self.cost
    
    def is_etf(self) -> bool:
        """是否ETF"""
        return self.asset_type == AssetType.ETF
    
    def has_position(self) -> bool:
        """是否持有仓位"""
        return self.shares > 0
    
    # ========== 更新方法 ==========
    
    def with_new_cost(self, new_shares: int, new_cost: float) -> "PositionModel":
        """创建更新成本后的新实例"""
        return PositionModel(
            symbol=self.symbol,
            shares=new_shares,
            cost=new_cost,
            base_shares=self.base_shares,
            asset_type=self.asset_type,
            updated_at=datetime.now(),
        )
    
    def with_base_shares(self, base_shares: int) -> "PositionModel":
        """创建更新底仓后的新实例"""
        return PositionModel(
            symbol=self.symbol,
            shares=self.shares,
            cost=self.cost,
            base_shares=base_shares,
            asset_type=self.asset_type,
            updated_at=datetime.now(),
        )
