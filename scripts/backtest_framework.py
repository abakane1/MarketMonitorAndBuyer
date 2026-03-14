#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测框架入口 (Backtest Framework)

v4.2.0 核心脚本
功能:
1. 标准化回测输入
2. 人机交易对比
3. 生成对比报告

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from capability_platform.backtest.engine import BacktestEngine, BacktestConfig
from capability_platform.backtest.metrics import calculate_metrics, compare_human_vs_system
from utils.data_fetcher import get_stock_daily_history

logger = logging.getLogger(__name__)


class BacktestFramework:
    """回测框架"""
    
    def __init__(self):
        self.results = []
    
    def load_strategy(self, strategy_file: str) -> callable:
        """加载策略"""
        # 简化实现，实际应动态加载策略模块
        from capability_platform.backtest.engine import example_strategy
        return example_strategy
    
    def run_backtest(self, symbol: str, start_date: str, end_date: str,
                    strategy_fn: callable,
                    initial_capital: float = 100000) -> Dict:
        """
        运行回测
        
        Args:
            symbol: 标的代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            strategy_fn: 策略函数
            initial_capital: 初始资金
            
        Returns:
            回测结果
        """
        logger.info(f"开始回测: {symbol} ({start_date} ~ {end_date})")
        
        # 1. 获取历史数据
        try:
            price_data = get_stock_daily_history(symbol, days=365)
            if price_data.empty:
                return {'success': False, 'error': '无法获取历史数据'}
        except Exception as e:
            return {'success': False, 'error': f'获取数据失败: {e}'}
        
        # 2. 过滤日期范围
        price_data['日期'] = pd.to_datetime(price_data['日期'])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        price_data = price_data[(price_data['日期'] >= start_dt) & 
                               (price_data['日期'] <= end_dt)]
        
        if price_data.empty:
            return {'success': False, 'error': '指定日期范围内无数据'}
        
        logger.info(f"数据条数: {len(price_data)}")
        
        # 3. 配置回测
        config = BacktestConfig(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital,
            commission_rate=0.0003,
            slippage=0.001
        )
        
        # 4. 运行回测
        engine = BacktestEngine(config)
        result = engine.run(strategy_fn, price_data)
        
        return {
            'success': True,
            'symbol': symbol,
            'period': f"{start_date} ~ {end_date}",
            'trades': len(result.trades),
            'metrics': result.metrics,
            'summary': result.summary()
        }
    
    def run_comparison(self, symbol: str, start_date: str, end_date: str,
                      human_trades: List[Dict],
                      strategy_fn: callable) -> Dict:
        """
        人机交易对比
        
        Args:
            symbol: 标的代码
            start_date: 开始日期
            end_date: 结束日期
            human_trades: 人工交易记录
            strategy_fn: 系统策略
            
        Returns:
            对比结果
        """
        # 运行系统回测
        system_result = self.run_backtest(symbol, start_date, end_date, strategy_fn)
        
        if not system_result['success']:
            return system_result
        
        # 对比结果
        comparison = {
            'symbol': symbol,
            'period': f"{start_date} ~ {end_date}",
            'human': {
                'trades_count': len(human_trades),
                'description': '人工交易记录'
            },
            'system': system_result,
            'conclusion': '系统策略回测完成，请对比人工交易记录'
        }
        
        return comparison
    
    def generate_report(self, result: Dict, format: str = 'text') -> str:
        """生成报告"""
        if format == 'json':
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        elif format == 'md':
            lines = [
                f"# 回测报告: {result.get('symbol', 'Unknown')}",
                "",
                f"**回测期间**: {result.get('period', 'N/A')}",
                f"**交易次数**: {result.get('trades', 0)}",
                "",
                "## 绩效指标",
            ]
            
            metrics = result.get('metrics', {})
            for key, value in metrics.items():
                if isinstance(value, float):
                    display_value = f"{value:.2%}" if 'return' in key or 'rate' in key else f"{value:.4f}"
                else:
                    display_value = str(value)
                lines.append(f"- **{key}**: {display_value}")
            
            return "\n".join(lines)
        
        else:  # text
            return result.get('summary', str(result))


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="回测框架")
    parser.add_argument("symbol", help="标的代码")
    parser.add_argument("--start", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=100000, help="初始资金")
    parser.add_argument("--strategy", default=None, help="策略文件路径")
    parser.add_argument("--format", choices=['text', 'json', 'md'], default='text',
                       help="输出格式")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--compare", help="人工交易记录JSON文件 (用于对比)")
    
    args = parser.parse_args()
    
    # 初始化框架
    framework = BacktestFramework()
    
    # 加载策略
    if args.strategy:
        strategy_fn = framework.load_strategy(args.strategy)
    else:
        from capability_platform.backtest.engine import example_strategy
        strategy_fn = example_strategy
    
    # 运行回测或对比
    if args.compare:
        # 加载人工交易记录
        with open(args.compare, 'r') as f:
            human_trades = json.load(f)
        
        result = framework.run_comparison(
            args.symbol, args.start, args.end,
            human_trades, strategy_fn
        )
    else:
        result = framework.run_backtest(
            args.symbol, args.start, args.end,
            strategy_fn, args.capital
        )
    
    # 生成报告
    report = framework.generate_report(result, format=args.format)
    
    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已保存: {args.output}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sys.exit(main())
