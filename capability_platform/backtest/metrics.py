# -*- coding: utf-8 -*-
"""
绩效指标计算模块 (Performance Metrics)

v4.2.0 核心模块
计算各类回测绩效指标:
- 收益类: 累计收益率、年化收益率、超额收益
- 风险类: 最大回撤、波动率、夏普比率、卡玛比率
- 交易类: 胜率、盈亏比、平均持仓周期

Author: AI Programmer
Date: 2026-03-14
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """绩效指标数据类"""
    # 收益类
    total_return: float = 0.0              # 累计收益率
    annualized_return: float = 0.0         # 年化收益率
    excess_return: float = 0.0             # 超额收益 (相对基准)
    
    # 风险类
    max_drawdown: float = 0.0              # 最大回撤
    max_drawdown_duration: int = 0         # 最大回撤持续天数
    volatility: float = 0.0                # 年化波动率
    sharpe_ratio: float = 0.0              # 夏普比率
    calmar_ratio: float = 0.0              # 卡玛比率
    
    # 交易类
    win_rate: float = 0.0                  # 胜率
    profit_loss_ratio: float = 0.0         # 盈亏比
    avg_trade_return: float = 0.0          # 平均交易收益
    total_trades: int = 0                  # 总交易次数
    avg_holding_period: float = 0.0        # 平均持仓周期
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            # 收益类
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'excess_return': self.excess_return,
            # 风险类
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'calmar_ratio': self.calmar_ratio,
            # 交易类
            'win_rate': self.win_rate,
            'profit_loss_ratio': self.profit_loss_ratio,
            'avg_trade_return': self.avg_trade_return,
            'total_trades': self.total_trades,
            'avg_holding_period': self.avg_holding_period
        }
    
    def __str__(self) -> str:
        """格式化输出"""
        lines = [
            "📊 绩效指标",
            "=" * 40,
            "【收益指标】",
            f"  累计收益率: {self.total_return:+.2%}",
            f"  年化收益率: {self.annualized_return:+.2%}",
            f"  超额收益: {self.excess_return:+.2%}",
            "",
            "【风险指标】",
            f"  最大回撤: {self.max_drawdown:.2%}",
            f"  回撤持续: {self.max_drawdown_duration}天",
            f"  年化波动率: {self.volatility:.2%}",
            f"  夏普比率: {self.sharpe_ratio:.2f}",
            f"  卡玛比率: {self.calmar_ratio:.2f}",
            "",
            "【交易指标】",
            f"  总交易次数: {self.total_trades}",
            f"  胜率: {self.win_rate:.1%}",
            f"  盈亏比: {self.profit_loss_ratio:.2f}",
            f"  平均持仓: {self.avg_holding_period:.1f}天"
        ]
        return "\n".join(lines)


def calculate_metrics(equity_curve: pd.DataFrame, 
                     trades: List,
                     config,
                     benchmark: Optional[pd.Series] = None) -> Dict:
    """
    计算绩效指标
    
    Args:
        equity_curve: 权益曲线 DataFrame (含equity列)
        trades: 交易记录列表
        config: 回测配置
        benchmark: 基准收益率序列 (可选)
        
    Returns:
        指标字典
    """
    if equity_curve.empty or 'equity' not in equity_curve.columns:
        return PerformanceMetrics().to_dict()
    
    metrics = PerformanceMetrics()
    
    # ===== 收益类指标 =====
    equity_series = equity_curve['equity']
    initial_value = config.initial_capital
    final_value = equity_series.iloc[-1]
    
    # 累计收益率
    metrics.total_return = (final_value - initial_value) / initial_value
    
    # 年化收益率
    total_days = (equity_series.index[-1] - equity_series.index[0]).days
    if total_days > 0:
        metrics.annualized_return = (1 + metrics.total_return) ** (365 / total_days) - 1
    
    # 超额收益
    if benchmark is not None:
        benchmark_return = (benchmark.iloc[-1] - benchmark.iloc[0]) / benchmark.iloc[0]
        metrics.excess_return = metrics.total_return - benchmark_return
    
    # ===== 风险类指标 =====
    # 计算日收益率
    if len(equity_series) > 1:
        daily_returns = equity_series.pct_change().dropna()
        
        # 年化波动率
        metrics.volatility = daily_returns.std() * np.sqrt(252)
        
        # 夏普比率 (假设无风险利率2%)
        risk_free_rate = 0.02
        if metrics.volatility > 0:
            metrics.sharpe_ratio = (metrics.annualized_return - risk_free_rate) / metrics.volatility
    
    # 最大回撤
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    metrics.max_drawdown = drawdown.min()
    
    # 最大回撤持续天数
    is_drawdown = drawdown < 0
    if is_drawdown.any():
        drawdown_groups = (is_drawdown != is_drawdown.shift()).cumsum()
        drawdown_durations = is_drawdown.groupby(drawdown_groups).sum()
        metrics.max_drawdown_duration = int(drawdown_durations.max())
    
    # 卡玛比率
    if abs(metrics.max_drawdown) > 0.001:
        metrics.calmar_ratio = metrics.annualized_return / abs(metrics.max_drawdown)
    
    # ===== 交易类指标 =====
    metrics.total_trades = len(trades)
    
    if trades:
        # 计算每笔交易收益
        trade_returns = []
        for i in range(0, len(trades) - 1, 2):  # 假设成对出现 (买+卖)
            if i + 1 < len(trades):
                buy = trades[i]
                sell = trades[i + 1]
                if buy.action == 'buy' and sell.action == 'sell':
                    profit = (sell.price - buy.price) * buy.shares
                    cost = buy.commission + sell.commission
                    trade_returns.append(profit - cost)
        
        if trade_returns:
            trade_returns = np.array(trade_returns)
            
            # 胜率
            wins = trade_returns > 0
            metrics.win_rate = wins.sum() / len(trade_returns)
            
            # 盈亏比
            avg_win = trade_returns[wins].mean() if wins.any() else 0
            avg_loss = abs(trade_returns[~wins].mean()) if (~wins).any() else 0.001
            metrics.profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
            
            # 平均交易收益
            metrics.avg_trade_return = trade_returns.mean()
            
            # 平均持仓周期 (简化计算)
            if len(trades) >= 2:
                holding_periods = []
                for i in range(0, len(trades) - 1, 2):
                    if i + 1 < len(trades):
                        buy_time = trades[i].timestamp
                        sell_time = trades[i + 1].timestamp
                        holding_days = (sell_time - buy_time).days
                        holding_periods.append(max(holding_days, 1))
                if holding_periods:
                    metrics.avg_holding_period = np.mean(holding_periods)
    
    return metrics.to_dict()


def calculate_annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    计算年化收益率
    
    Args:
        returns: 收益率序列
        periods_per_year: 每年周期数 (日:252, 周:52, 月:12)
    """
    total_return = (1 + returns).prod() - 1
    n_periods = len(returns)
    if n_periods == 0:
        return 0.0
    
    # 年化
    years = n_periods / periods_per_year
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0
    
    return annualized


def calculate_beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    计算Beta系数
    
    Args:
        returns: 策略收益率
        benchmark_returns: 基准收益率
    """
    # 对齐数据
    aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0
    
    covariance = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    benchmark_variance = aligned.iloc[:, 1].var()
    
    if benchmark_variance == 0:
        return 0.0
    
    return covariance / benchmark_variance


def calculate_alpha(returns: pd.Series, benchmark_returns: pd.Series, 
                   risk_free_rate: float = 0.02) -> float:
    """
    计算Alpha (超额收益)
    
    Args:
        returns: 策略收益率
        benchmark_returns: 基准收益率
        risk_free_rate: 无风险利率
    """
    beta = calculate_beta(returns, benchmark_returns)
    
    strategy_annual = calculate_annualized_return(returns)
    benchmark_annual = calculate_annualized_return(benchmark_returns)
    
    # CAPM Alpha
    alpha = strategy_annual - (risk_free_rate + beta * (benchmark_annual - risk_free_rate))
    
    return alpha


# 人机对比功能
def compare_human_vs_system(human_trades: List, 
                           system_result,
                           period: str) -> Dict:
    """
    对比人工交易和系统策略的收益差异
    
    Args:
        human_trades: 人工交易记录
        system_result: 系统回测结果
        period: 对比期间
        
    Returns:
        对比报告
    """
    # 计算人工交易绩效
    # (简化实现，实际需要更复杂计算)
    
    return {
        'period': period,
        'human_trades_count': len(human_trades),
        'system_trades_count': len(system_result.trades),
        'system_metrics': system_result.metrics,
        'conclusion': '系统策略 vs 人工交易对比完成'
    }


if __name__ == "__main__":
    # 测试绩效指标计算
    print("🧪 测试绩效指标计算")
    print("=" * 50)
    
    # 创建测试数据
    import pandas as pd
    from datetime import datetime, timedelta
    
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    equity = 100000 * (1 + np.cumsum(np.random.randn(30) * 0.01))
    
    equity_curve = pd.DataFrame({
        'equity': equity
    }, index=dates)
    
    # 模拟交易
    class MockTrade:
        def __init__(self, action, price, shares):
            self.action = action
            self.price = price
            self.shares = shares
            self.timestamp = datetime.now()
            self.commission = price * shares * 0.0003
    
    trades = [
        MockTrade('buy', 10.0, 1000),
        MockTrade('sell', 11.0, 1000),
        MockTrade('buy', 10.5, 1000),
        MockTrade('sell', 11.5, 1000),
    ]
    
    from dataclasses import dataclass
    @dataclass
    class MockConfig:
        initial_capital: float = 100000.0
    
    config = MockConfig()
    
    metrics = calculate_metrics(equity_curve, trades, config)
    
    print("\n计算结果:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2%}" if 'return' in key or 'rate' in key else f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
