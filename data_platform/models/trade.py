# -*- coding: utf-8 -*-
"""
交易记录数据模型

所有交易操作的唯一事实来源。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .base import BaseModel, TradeAction, AssetType


@dataclass(frozen=True)
class TradeModel(BaseModel):
    """
    交易记录模型
    """
    
    symbol: str = ''
    action: TradeAction = TradeAction.BUY
    price: float = 0.0
    amount: int = 0
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    fee: float = 0.0
    stamp_duty: float = 0.0
    transfer_fee: float = 0.0
    note: str = ""
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
            'id': self.id,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'type': self.action.value,
            'price': self.price,
            'amount': self.amount,
            'fee': self.fee,
            'stamp_duty': self.stamp_duty,
            'transfer_fee': self.transfer_fee,
            'note': self.note,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeModel":
        action_value = data.get('type', 'buy')
        # 兼容旧数据
        action_map = {
            'buy': TradeAction.BUY,
            'sell': TradeAction.SELL,
            '买入': TradeAction.BUY,
            '卖出': TradeAction.SELL,
            'override': TradeAction.OVERRIDE,
            'base_position': TradeAction.BASE_POSITION,
        }
        action = action_map.get(action_value.lower(), TradeAction.BUY)
        
        # 解析时间
        ts_str = data.get('timestamp', '')
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()
        
        return cls(
            id=data.get('id'),
            symbol=data['symbol'],
            action=action,
            price=float(data.get('price', 0)),
            amount=int(data.get('amount', 0)),
            timestamp=timestamp,
            fee=float(data.get('fee', 0)),
            stamp_duty=float(data.get('stamp_duty', 0)),
            transfer_fee=float(data.get('transfer_fee', 0)),
            note=data.get('note', ''),
        )
    
    def validate(self) -> tuple[bool, str]:
        """数据校验"""
        if not self.symbol:
            return False, "股票代码不能为空"
        
        if self.price <= 0:
            return False, f"成交价格必须大于0: {self.price}"
        
        if self.amount <= 0:
            return False, f"成交数量必须大于0: {self.amount}"
        
        if self.fee < 0 or self.stamp_duty < 0 or self.transfer_fee < 0:
            return False, "费用不能为负"
        
        return True, ""
    
    # ========== 计算属性 ==========
    
    @property
    def trade_value(self) -> float:
        """成交金额 = 价格 * 数量"""
        return self.price * self.amount
    
    @property
    def total_cost(self) -> float:
        """总成本 = 成交金额 + 各项费用"""
        return self.trade_value + self.fee + self.stamp_duty + self.transfer_fee
    
    @property
    def net_amount(self) -> float:
        """净额（卖出时扣除费用）"""
        if self.action.is_sell():
            return self.trade_value - self.fee - self.stamp_duty - self.transfer_fee
        return self.trade_value
    
    def is_buy(self) -> bool:
        """是否买入"""
        return self.action.is_buy()
    
    def is_sell(self) -> bool:
        """是否卖出"""
        return self.action.is_sell()
    
    def is_override(self) -> bool:
        """是否修正"""
        return self.action == TradeAction.OVERRIDE
    
    def affects_position(self) -> bool:
        """是否影响持仓"""
        return self.action.affects_position()
