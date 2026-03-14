#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绩效归因分析入口 (Performance Attribution)

v4.2.0 核心脚本
功能:
1. Brinson三层归因
2. 行业归因分析
3. 风格因子归因
4. 生成归因报告

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from capability_platform.analytics.brinson_attribution import (
    calculate_brinson_attribution, quick_attribution_analysis
)

logger = logging.getLogger(__name__)


class PerformanceAttributionAnalyzer:
    """绩效归因分析器"""
    
    def __init__(self):
        self.results = {}
    
    def analyze_portfolio(self, 
                         portfolio_data: Dict,
                         benchmark_data: Dict,
                         method: str = 'brinson') -> Dict:
        """
        分析组合绩效归因
        
        Args:
            portfolio_data: 组合数据
            benchmark_data: 基准数据
            method: 归因方法 (brinson)
            
        Returns:
            分析结果
        """
        if method == 'brinson':
            return self._brinson_analysis(portfolio_data, benchmark_data)
        else:
            return {'error': f'不支持的归因方法: {method}'}
    
    def _brinson_analysis(self, portfolio: Dict, benchmark: Dict) -> Dict:
        """Brinson归因分析"""
        try:
            # 转换为Series
            wp = pd.Series(portfolio.get('sector_weights', {}))
            rp = pd.Series(portfolio.get('sector_returns', {}))
            wb = pd.Series(benchmark.get('sector_weights', {}))
            rb = pd.Series(benchmark.get('sector_returns', {}))
            
            # 计算归因
            from capability_platform.analytics.brinson_attribution import BrinsonAttribution
            attribution = calculate_brinson_attribution(wp, rp, wb, rb)
            
            return {
                'method': 'brinson',
                'success': True,
                'portfolio_return': (wp * rp).sum(),
                'benchmark_return': (wb * rb).sum(),
                'excess_return': attribution.total_excess_return,
                'allocation_effect': attribution.allocation_effect,
                'selection_effect': attribution.selection_effect,
                'interaction_effect': attribution.interaction_effect,
                'sector_contributions': attribution.sector_contributions,
                'summary': attribution.summary()
            }
            
        except Exception as e:
            logger.error(f"Brinson分析失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def analyze_from_trades(self, 
                           trades: List[Dict],
                           benchmark_symbol: str = '000300',  # 沪深300
                           period: str = '30d') -> Dict:
        """
        从交易记录分析归因
        
        Args:
            trades: 交易记录列表
            benchmark_symbol: 基准指数代码
            period: 分析期间
            
        Returns:
            分析结果
        """
        # 简化实现
        # 实际应该根据交易记录重建持仓，然后计算归因
        
        return {
            'method': 'trade_based',
            'trades_count': len(trades),
            'period': period,
            'note': '基于交易记录的归因分析 (简化实现)',
            'recommendation': '建议使用详细持仓数据进行更精确的归因分析'
        }
    
    def generate_report(self, result: Dict, format: str = 'text') -> str:
        """生成报告"""
        if format == 'json':
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        
        elif format == 'md':
            lines = [
                "# 绩效归因分析报告",
                "",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"**归因方法**: {result.get('method', 'Unknown')}",
                "",
                "## 收益概况",
                f"- 组合收益: {result.get('portfolio_return', 0):+.2%}",
                f"- 基准收益: {result.get('benchmark_return', 0):+.2%}",
                f"- 超额收益: {result.get('excess_return', 0):+.2%}",
                "",
                "## Brinson归因",
                f"- 资产配置收益: {result.get('allocation_effect', 0):+.2%}",
                f"- 个股选择收益: {result.get('selection_effect', 0):+.2%}",
                f"- 交互收益: {result.get('interaction_effect', 0):+.2%}",
            ]
            
            # 行业贡献
            sector_contrib = result.get('sector_contributions', {})
            if sector_contrib:
                lines.extend(["", "## 行业贡献"])
                for sector, data in sector_contrib.items():
                    total = data['allocation'] + data['selection'] + data['interaction']
                    lines.append(f"- **{sector}**: {total:+.2%}")
            
            return "\n".join(lines)
        
        else:  # text
            return result.get('summary', str(result))


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="绩效归因分析工具")
    parser.add_argument("--portfolio", required=True, help="组合数据JSON文件")
    parser.add_argument("--benchmark", required=True, help="基准数据JSON文件")
    parser.add_argument("--method", choices=['brinson'], default='brinson',
                       help="归因方法")
    parser.add_argument("--format", choices=['text', 'json', 'md'], default='text',
                       help="输出格式")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 加载数据
    try:
        with open(args.portfolio, 'r') as f:
            portfolio_data = json.load(f)
        with open(args.benchmark, 'r') as f:
            benchmark_data = json.load(f)
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return 1
    
    # 运行分析
    analyzer = PerformanceAttributionAnalyzer()
    result = analyzer.analyze_portfolio(
        portfolio_data,
        benchmark_data,
        args.method
    )
    
    # 生成报告
    report = analyzer.generate_report(result, format=args.format)
    
    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已保存: {args.output}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    # 测试
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) == 1:
        # 无参数时运行测试
        print("🧪 测试绩效归因分析")
        print("=" * 60)
        
        # 示例数据
        portfolio_data = {
            'sector_weights': {'科技': 0.5, '金融': 0.3, '消费': 0.2},
            'sector_returns': {'科技': 0.15, '金融': 0.05, '消费': 0.08}
        }
        
        benchmark_data = {
            'sector_weights': {'科技': 0.4, '金融': 0.4, '消费': 0.2},
            'sector_returns': {'科技': 0.10, '金融': 0.06, '消费': 0.07}
        }
        
        analyzer = PerformanceAttributionAnalyzer()
        result = analyzer.analyze_portfolio(portfolio_data, benchmark_data)
        
        print(analyzer.generate_report(result, format='text'))
    else:
        sys.exit(main())
