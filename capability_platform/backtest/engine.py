# -*- coding: utf-8 -*-
"""
回测引擎 (Backtest Engine)

v4.2.0 核心模块
功能:
1. 分钟级行情回测
2. 策略执行模拟
3. 交易记录生成
4. 绩效指标计算

Author: AI Programmer
Date: 2026-03-14
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """回测配置"""
    symbol: str                          # 标的代码
    start_date: datetime                 # 开始日期
    end_date: datetime                   # 结束日期
    initial_capital: float = 100000.0    # 初始资金
    commission_rate: float = 0.0003      # 手续费率 (万3)
    slippage: float = 0.001              # 滑点 (0.1%)
    position_pct: float = 1.0            # 仓位比例


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    action: str                          # buy/sell
    price: float
    shares: int
    commission: float
    slippage: float
    total_value: float


@dataclass
class BacktestResult:
    """回测结果"""
    config: BacktestConfig
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def summary(self) -> str:
        """生成摘要报告"""
        lines = [
            "📊 回测结果摘要",
            "=" * 50,
            f"标的: {self.config.symbol}",
            f"期间: {self.config.start_date.date()} ~ {self.config.end_date.date()}",
            f"初始资金: ¥{self.config.initial_capital:,.2f}",
            f"交易次数: {len(self.trades)}",
            "-" * 50,
            "绩效指标:",
        ]
        
        for key, value in self.metrics.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.2%}" if 'return' in key or 'rate' in key else f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)


class BacktestEngine:
    """
    回测引擎
    
    使用示例:
        engine = BacktestEngine(config)
        result = engine.run(strategy_func, price_data)
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.cash = config.initial_capital
        self.position = 0
        self.trades: List[TradeRecord] = []
        self.equity_history: List[Dict] = []
    
    def reset(self):
        """重置状态"""
        self.cash = self.config.initial_capital
        self.position = 0
        self.trades = []
        self.equity_history = []
    
    def run(self, strategy_fn: Callable, price_data: pd.DataFrame) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy_fn: 策略函数 (context, bar) -> signal
            price_data: 价格数据 DataFrame (分钟级或日级)
            
        Returns:
            回测结果
        """
        self.reset()
        
        if price_data.empty:
            logger.error("价格数据为空")
            return BacktestResult(config=self.config)
        
        # 确保数据按时间排序
        price_data = price_data.sort_values('时间' if '时间' in price_data.columns else '日期')
        
        logger.info(f"开始回测: {self.config.symbol}, 数据条数: {len(price_data)}")
        
        # 逐条遍历数据
        for idx, row in price_data.iterrows():
            timestamp = pd.to_datetime(row.get('时间', row.get('日期', idx)))
            
            # 构建当前bar
            bar = {
                'timestamp': timestamp,
                'open': float(row.get('开盘', row.get('open', 0))),
                'high': float(row.get('最高', row.get('high', 0))),
                'low': float(row.get('最低', row.get('low', 0))),
                'close': float(row.get('收盘', row.get('close', 0))),
                'volume': float(row.get('成交量', row.get('volume', 0)))
            }
            
            # 构建上下文
            context = {
                'cash': self.cash,
                'position': self.position,
                'trades': self.trades,
                'config': self.config
            }
            
            # 获取策略信号
            try:
                signal = strategy_fn(context, bar)
            except Exception as e:
                logger.error(f"策略执行错误: {e}")
                signal = None
            
            # 执行交易
            if signal:
                self._execute_signal(signal, bar)
            
            # 记录权益
            equity = self._calculate_equity(bar['close'])
            self.equity_history.append({
                'timestamp': timestamp,
                'equity': equity,
                'cash': self.cash,
                'position': self.position,
                'price': bar['close']
            })
        
        # 生成结果
        result = self._generate_result()
        logger.info(f"回测完成: 交易{len(self.trades)}次, 最终权益¥{result.equity_curve['equity'].iloc[-1]:,.2f}")
        
        return result
    
    def _execute_signal(self, signal: Dict, bar: Dict):
        """执行交易信号"""
        action = signal.get('action', '').lower()
        price = bar['close']
        
        # 应用滑点
        if action == 'buy':
            executed_price = price * (1 + self.config.slippage)
        elif action == 'sell':
            executed_price = price * (1 - self.config.slippage)
        else:
            return
        
        # 计算交易数量
        if action == 'buy':
            # 计算可买入数量
            max_value = self.cash * self.config.position_pct
            shares = int(max_value / executed_price / 100) * 100  # 整手
            if shares <= 0:
                return
            
            # 计算成本
            total_value = shares * executed_price
            commission = total_value * self.config.commission_rate
            
            if total_value + commission > self.cash:
                return
            
            # 执行买入
            self.cash -= (total_value + commission)
            self.position += shares
            
        elif action == 'sell':
            shares = signal.get('shares', self.position)
            shares = min(shares, self.position)
            if shares <= 0:
                return
            
            # 计算收入
            total_value = shares * executed_price
            commission = total_value * self.config.commission_rate
            
            # 执行卖出
            self.cash += (total_value - commission)
            self.position -= shares
        
        # 记录交易
        self.trades.append(TradeRecord(
            timestamp=bar['timestamp'],
            action=action,
            price=executed_price,
            shares=shares,
            commission=commission,
            slippage=self.config.slippage,
            total_value=total_value
        ))
    
    def _calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        position_value = self.position * current_price
        return self.cash + position_value
    
    def _generate_result(self) -> BacktestResult:
        """生成回测结果"""
        # 构建权益曲线
        if self.equity_history:
            equity_df = pd.DataFrame(self.equity_history)
            equity_df.set_index('timestamp', inplace=True)
        else:
            equity_df = pd.DataFrame()
        
        # 计算绩效指标
        from .metrics import calculate_metrics
        metrics = calculate_metrics(equity_df, self.trades, self.config)
        
        return BacktestResult(
            config=self.config,
            trades=self.trades,
            equity_curve=equity_df,
            metrics=metrics
        )


# 简单策略示例
def example_strategy(context: Dict, bar: Dict) -> Optional[Dict]:
    """
    示例策略: 均线交叉
    
    这是一个简单的双均线策略示例
    """
    # 这里应该维护均线状态，简化示例
    # 实际策略需要更复杂的逻辑
    
    position = context['position']
    cash = context['cash']
    
    # 简化的随机策略 (仅用于测试)
    import random
    if random.random() < 0.1:  # 10%概率触发
        if position == 0 and cash > 0:
            return {'action': 'buy'}
        elif position > 0:
            return {'action': 'sell', 'shares': position}
    
    return None


if __name__ == "__main__":
    # 测试回测引擎
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 测试回测引擎")
    print("=" * 50)
    
    # 创建测试数据
    dates = pd.date_range(start='2024-01-01', end='2024-01-30', freq='D')
    np.random.seed(42)
    prices = 10 + np.cumsum(np.random.randn(len(dates)) * 0.1)
    
    test_data = pd.DataFrame({
        '日期': dates,
        '开盘': prices * (1 + np.random.randn(len(dates)) * 0.01),
        '最高': prices * (1 + abs(np.random.randn(len(dates))) * 0.02),
        '最低': prices * (1 - abs(np.random.randn(len(dates))) * 0.02),
        '收盘': prices,
        '成交量': np.random.randint(1000, 10000, len(dates))
    })
    
    # 配置
    config = BacktestConfig(
        symbol="TEST",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 30),
        initial_capital=100000
    )
    
    # 运行回测
    engine = BacktestEngine(config)
    result = engine.run(example_strategy, test_data)
    
    # 输出结果
    print(result.summary())
