# -*- coding: utf-8 -*-
"""
数据中台 (Data Platform) - v4.0.0-simplified

统一数据管理层，提供：
1. 统一数据模型
2. 统一数据服务
3. 数据一致性保障

使用示例:
    from data_platform import PositionService, TradeService
    
    # 获取持仓
    pos_service = PositionService()
    position = pos_service.get('588200')
    
    # 记录交易
    trade_service = TradeService()
    trade = TradeModel(symbol='588200', action=TradeAction.BUY, ...)
    success, msg = trade_service.execute(trade)
"""

from .models import (
    PositionModel,
    TradeModel,
    QuoteModel,
    TradeAction,
    AssetType
)

from .services import (
    PositionService,
    TradeService,
)

__version__ = '4.0.0-simplified'
__all__ = [
    # Models
    'PositionModel',
    'TradeModel', 
    'QuoteModel',
    'TradeAction',
    'AssetType',
    # Services
    'PositionService',
    'TradeService',
]
