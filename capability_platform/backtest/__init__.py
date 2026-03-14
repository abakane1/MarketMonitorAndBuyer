# -*- coding: utf-8 -*-
"""
回测引擎模块 (Backtest Engine)

v4.2.0 新增模块
提供策略回测与绩效分析能力
"""

from .engine import BacktestEngine
from .metrics import calculate_metrics, PerformanceMetrics
from .simulator import TradeSimulator

__all__ = [
    'BacktestEngine',
    'calculate_metrics',
    'PerformanceMetrics',
    'TradeSimulator'
]
