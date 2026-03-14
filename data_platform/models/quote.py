# -*- coding: utf-8 -*-
"""
行情数据模型

实时行情的唯一事实来源。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .base import BaseModel, AssetType


@dataclass(frozen=True)
class QuoteModel(BaseModel):
    """
    行情数据模型
    """
    
    symbol: str = ''
    price: float = 0.0
    pre_close: float = 0.0
    name: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    change_pct: float = 0.0
    change_amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
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
            'name': self.name,
            'price': self.price,
            'pre_close': self.pre_close,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'amount': self.amount,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuoteModel":
        return cls(
            symbol=data.get('symbol', data.get('代码', '')),
            name=data.get('name', data.get('名称', '')),
            price=float(data.get('price', data.get('最新价', 0))),
            pre_close=float(data.get('pre_close', data.get('昨收', 0))),
            open=float(data.get('open', data.get('今开', data.get('开盘价', 0)))),
            high=float(data.get('high', data.get('最高', data.get('最高价', 0)))),
            low=float(data.get('low', data.get('最低', data.get('最低价', 0)))),
            volume=float(data.get('volume', data.get('成交量', 0))),
            amount=float(data.get('amount', data.get('成交额', 0))),
            change_pct=float(data.get('change_pct', data.get('涨跌幅', 0))),
            change_amount=float(data.get('change_amount', data.get('涨跌额', 0))),
            source=data.get('source', 'unknown'),
        )
    
    def validate(self) -> tuple[bool, str]:
        """数据校验"""
        if not self.symbol:
            return False, "股票代码不能为空"
        
        if self.price <= 0:
            return False, f"最新价必须大于0: {self.price}"
        
        if self.pre_close <= 0:
            return False, f"昨收必须大于0: {self.pre_close}"
        
        return True, ""
    
    # ========== 计算属性 ==========
    
    @property
    def change(self) -> float:
        """涨跌额 = 现价 - 昨收"""
        return self.price - self.pre_close
    
    @property
    def change_percent(self) -> float:
        """涨跌幅 = (现价 - 昨收) / 昨收 * 100"""
        if self.pre_close <= 0:
            return 0.0
        return (self.price - self.pre_close) / self.pre_close * 100
    
    @property
    def is_up(self) -> bool:
        """是否上涨"""
        return self.price > self.pre_close
    
    @property
    def is_down(self) -> bool:
        """是否下跌"""
        return self.price < self.pre_close
    
    @property
    def is_flat(self) -> bool:
        """是否平盘"""
        return self.price == self.pre_close
    
    @property
    def amplitude(self) -> float:
        """振幅 = (最高 - 最低) / 昨收 * 100"""
        if self.pre_close <= 0 or self.high <= 0 or self.low <= 0:
            return 0.0
        return (self.high - self.low) / self.pre_close * 100
    
    # ========== 持仓相关计算 ==========
    
    def today_pnl(self, shares: int) -> float:
        """计算今日盈亏"""
        return shares * self.change
    
    def floating_pnl(self, shares: int, cost: float) -> float:
        """计算浮动盈亏"""
        return shares * (self.price - cost)
    
    def market_value(self, shares: int) -> float:
        """计算市值"""
        return shares * self.price
