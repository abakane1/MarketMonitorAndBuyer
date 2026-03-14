# -*- coding: utf-8 -*-
"""
基础模型类和枚举定义
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, Any


class AssetType(Enum):
    """资产类型"""
    STOCK = "stock"      # 股票
    ETF = "etf"          # ETF
    FUND = "fund"        # 基金
    BOND = "bond"        # 债券
    OPTION = "option"    # 期权
    FUTURES = "futures"  # 期货
    
    @classmethod
    def from_symbol(cls, symbol: str) -> "AssetType":
        """根据代码判断资产类型"""
        from utils.asset_classifier import is_etf
        if is_etf(symbol):
            return cls.ETF
        return cls.STOCK


class TradeAction(Enum):
    """交易动作"""
    BUY = "buy"           # 买入
    SELL = "sell"         # 卖出
    OVERRIDE = "override" # 持仓修正
    BASE_POSITION = "base_position"  # 设置底仓
    
    def is_buy(self) -> bool:
        return self in (TradeAction.BUY,)
    
    def is_sell(self) -> bool:
        return self in (TradeAction.SELL,)
    
    def affects_position(self) -> bool:
        """是否影响持仓数量"""
        return self in (TradeAction.BUY, TradeAction.SELL, TradeAction.OVERRIDE)


@dataclass(frozen=True)
class BaseModel(ABC):
    """
    基础数据模型
    
    所有模型都是不可变的（frozen=True），确保数据一致性。
    更新数据时创建新实例。
    """
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """从字典创建"""
        pass
    
    def validate(self) -> tuple[bool, str]:
        """
        数据校验
        
        Returns:
            (是否通过, 错误信息)
        """
        return True, ""
