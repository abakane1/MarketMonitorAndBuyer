# -*- coding: utf-8 -*-
"""
能力中台 (Capability Platform) - v4.0.0

统一算法和业务逻辑层，提供：
1. 统一计算引擎
2. 统一分析引擎
3. 统一策略引擎
4. 统一风控引擎

使用示例:
    from capability_platform.calculators import PositionCalculator, PnLCalculator, FeeCalculator
    from capability_platform.risk import TradeLimit
    
    # 计算新持仓
    new_shares, new_cost = PositionCalculator.calculate_new_position(...)
    
    # 计算盈亏
    pnl = PnLCalculator.calculate_floating_pnl(...)
"""

from .calculators import (
    PositionCalculator,
    PnLCalculator,
    FeeCalculator,
)

from .risk import (
    check_trade_limit,
    check_position_limit,
    set_trade_limit_enabled,
    ENABLE_TRADE_LIMIT,
)

__version__ = '4.0.0-simplified'
__all__ = [
    # Calculators
    'PositionCalculator',
    'PnLCalculator',
    'FeeCalculator',
    # Risk
    'check_trade_limit',
    'check_position_limit',
    'set_trade_limit_enabled',
    'ENABLE_TRADE_LIMIT',
]
