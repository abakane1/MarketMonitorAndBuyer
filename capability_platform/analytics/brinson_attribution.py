# -*- coding: utf-8 -*-
"""
Brinson绩效归因分析 (Brinson Attribution)

v4.2.0 核心模块
分解投资收益为:
- 资产配置收益 (Allocation Effect)
- 个股选择收益 (Selection Effect)
- 交互收益 (Interaction Effect)

Author: AI Programmer
Date: 2026-03-14
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BrinsonAttribution:
    """Brinson归因结果"""
    # 各效应收益
    allocation_effect: float = 0.0       # 资产配置收益
    selection_effect: float = 0.0        # 个股选择收益
    interaction_effect: float = 0.0      # 交互收益
    total_excess_return: float = 0.0     # 总超额收益
    
    # 详细分解
    sector_contributions: Dict[str, Dict] = None
    
    def summary(self) -> str:
        """生成摘要"""
        lines = [
            "📊 Brinson绩效归因",
            "=" * 40,
            f"资产配置收益: {self.allocation_effect:+.2%}",
            f"个股选择收益: {self.selection_effect:+.2%}",
            f"交互收益:     {self.interaction_effect:+.2%}",
            "-" * 40,
            f"总超额收益:   {self.total_excess_return:+.2%}",
        ]
        
        # 验证
        total = self.allocation_effect + self.selection_effect + self.interaction_effect
        if abs(total - self.total_excess_return) > 0.0001:
            lines.append(f"验证: {total:+.2%} (应有{self.total_excess_return:+.2%})")
        
        return "\n".join(lines)


def calculate_brinson_attribution(
    portfolio_weights: pd.Series,
    portfolio_returns: pd.Series,
    benchmark_weights: pd.Series,
    benchmark_returns: pd.Series
) -> BrinsonAttribution:
    """
    计算Brinson归因
    
    公式:
    - 资产配置效应 = Σ(Wp_i - Wb_i) * Rb_i
    - 个股选择效应 = ΣWb_i * (Rp_i - Rb_i)
    - 交互效应 = Σ(Wp_i - Wb_i) * (Rp_i - Rb_i)
    
    Args:
        portfolio_weights: 组合权重 (sector -> weight)
        portfolio_returns: 组合收益 (sector -> return)
        benchmark_weights: 基准权重 (sector -> weight)
        benchmark_returns: 基准收益 (sector -> return)
        
    Returns:
        Brinson归因结果
    """
    # 对齐数据
    sectors = portfolio_weights.index.union(benchmark_weights.index)
    
    wp = portfolio_weights.reindex(sectors, fill_value=0)
    rp = portfolio_returns.reindex(sectors, fill_value=0)
    wb = benchmark_weights.reindex(sectors, fill_value=0)
    rb = benchmark_returns.reindex(sectors, fill_value=0)
    
    # 计算各效应
    allocation = ((wp - wb) * rb).sum()
    selection = (wb * (rp - rb)).sum()
    interaction = ((wp - wb) * (rp - rb)).sum()
    
    # 总超额收益
    total_portfolio_return = (wp * rp).sum()
    total_benchmark_return = (wb * rb).sum()
    total_excess = total_portfolio_return - total_benchmark_return
    
    # 各行业贡献
    sector_contributions = {}
    for sector in sectors:
        sector_contributions[sector] = {
            'portfolio_weight': wp[sector],
            'portfolio_return': rp[sector],
            'benchmark_weight': wb[sector],
            'benchmark_return': rb[sector],
            'allocation': (wp[sector] - wb[sector]) * rb[sector],
            'selection': wb[sector] * (rp[sector] - rb[sector]),
            'interaction': (wp[sector] - wb[sector]) * (rp[sector] - rb[sector])
        }
    
    return BrinsonAttribution(
        allocation_effect=allocation,
        selection_effect=selection,
        interaction_effect=interaction,
        total_excess_return=total_excess,
        sector_contributions=sector_contributions
    )


def analyze_sector_performance(
    holdings: pd.DataFrame,
    prices: pd.DataFrame,
    sector_mapping: Dict[str, str]
) -> pd.DataFrame:
    """
    分析各行业表现
    
    Args:
        holdings: 持仓数据 (date, symbol, shares)
        prices: 价格数据 (date, symbol, price)
        sector_mapping: 股票->行业映射
        
    Returns:
        行业表现DataFrame
    """
    # 简化实现
    # 实际应该根据持仓和价格计算各行业收益
    
    results = []
    for symbol, sector in sector_mapping.items():
        results.append({
            'symbol': symbol,
            'sector': sector,
            'weight': 0.0,  # 需要计算
            'return': 0.0   # 需要计算
        })
    
    return pd.DataFrame(results)


# 行业分类映射 (简化版)
SECTOR_MAPPING = {
    # 芯片/半导体相关
    '588200': '芯片',
    '588710': '半导体设备',
    '588750': '芯片',
    # 其他ETF...
}


def quick_attribution_analysis(
    portfolio_return: float,
    benchmark_return: float,
    sector_weights_portfolio: Dict[str, float],
    sector_weights_benchmark: Dict[str, float],
    sector_returns: Dict[str, float]
) -> Dict:
    """
    快速归因分析
    
    当没有详细持仓数据时的简化分析
    
    Args:
        portfolio_return: 组合总收益
        benchmark_return: 基准总收益
        sector_weights_portfolio: 组合行业权重
        sector_weights_benchmark: 基准行业权重
        sector_returns: 各行业收益
        
    Returns:
        简化归因结果
    """
    # 转换为Series
    wp = pd.Series(sector_weights_portfolio)
    wb = pd.Series(sector_weights_benchmark)
    rs = pd.Series(sector_returns)
    
    # 假设组合和基准在各行业内的收益相同 (简化)
    rp = rs
    rb = rs
    
    # 计算归因
    attribution = calculate_brinson_attribution(wp, rp, wb, rb)
    
    return {
        'total_return': portfolio_return,
        'benchmark_return': benchmark_return,
        'excess_return': portfolio_return - benchmark_return,
        'allocation_effect': attribution.allocation_effect,
        'selection_effect': attribution.selection_effect,
        'interaction_effect': attribution.interaction_effect,
        'summary': attribution.summary()
    }


if __name__ == "__main__":
    # 测试Brinson归因
    print("🧪 测试Brinson绩效归因")
    print("=" * 60)
    
    # 示例数据
    # 假设有3个行业: 科技、金融、消费
    portfolio_weights = pd.Series({
        '科技': 0.50,
        '金融': 0.30,
        '消费': 0.20
    })
    
    portfolio_returns = pd.Series({
        '科技': 0.15,   # 科技板块收益15%
        '金融': 0.05,   # 金融板块收益5%
        '消费': 0.08    # 消费板块收益8%
    })
    
    benchmark_weights = pd.Series({
        '科技': 0.40,
        '金融': 0.40,
        '消费': 0.20
    })
    
    benchmark_returns = pd.Series({
        '科技': 0.10,   # 基准科技收益10%
        '金融': 0.06,   # 基准金融收益6%
        '消费': 0.07    # 基准消费收益7%
    })
    
    # 计算归因
    result = calculate_brinson_attribution(
        portfolio_weights,
        portfolio_returns,
        benchmark_weights,
        benchmark_returns
    )
    
    print(result.summary())
    
    print("\n📊 各行业贡献:")
    print("-" * 60)
    for sector, contrib in result.sector_contributions.items():
        print(f"\n{sector}:")
        print(f"  组合权重: {contrib['portfolio_weight']:.1%}, 收益: {contrib['portfolio_return']:.1%}")
        print(f"  基准权重: {contrib['benchmark_weight']:.1%}, 收益: {contrib['benchmark_return']:.1%}")
        print(f"  资产配置: {contrib['allocation']:+.2%}")
        print(f"  个股选择: {contrib['selection']:+.2%}")
        print(f"  交互效应: {contrib['interaction']:+.2%}")
