#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量风控分析脚本 (Batch Risk Audit)

v4.1.0 Week 3 - Dual-Expert Architecture Phase 2
功能:
1. 批量对多个标的进行红蓝双专家分析
2. 输出结构化风控报告
3. 支持命令行批量操作

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.ai_interface import UnifiedAIInterface, StrategyGenerator, RiskAuditor
from capability_platform.risk.dual_expert_decision import DualExpertDecisionEngine, BlueAdvice, RedAudit
from utils.data_fetcher import get_stock_realtime_info

logger = logging.getLogger(__name__)


class BatchRiskAnalyzer:
    """批量风险分析器"""
    
    def __init__(self):
        self.ai = UnifiedAIInterface()
        self.strategy_gen = StrategyGenerator()
        self.risk_auditor = RiskAuditor()
        self.decision_engine = DualExpertDecisionEngine()
    
    def analyze_symbol(self, symbol: str) -> Dict:
        """
        分析单个标的
        
        Args:
            symbol: 标的代码
            
        Returns:
            分析结果
        """
        print(f"\n🔄 分析 {symbol}...")
        
        # 1. 获取行情数据
        quote = get_stock_realtime_info(symbol)
        if not quote:
            return {
                'symbol': symbol,
                'success': False,
                'error': '获取行情失败'
            }
        
        context = {
            'symbol': symbol,
            'name': quote.get('name', symbol),
            'price': quote.get('price', 0),
            'pre_close': quote.get('pre_close', 0),
            'change_pct': (quote.get('price', 0) - quote.get('pre_close', 0)) / quote.get('pre_close', 1) * 100
        }
        
        # 2. 蓝军生成策略
        print(f"   🟢 蓝军策略生成...")
        strategy_result = self.strategy_gen.generate_strategy(symbol, context)
        
        if not strategy_result['success']:
            return {
                'symbol': symbol,
                'success': False,
                'error': f"策略生成失败: {strategy_result.get('error')}"
            }
        
        strategy = strategy_result['strategy']
        
        # 3. 红军审计
        print(f"   🔴 红军风险审计...")
        audit_result = self.risk_auditor.audit_strategy(strategy, context)
        
        if not audit_result['success']:
            return {
                'symbol': symbol,
                'success': False,
                'error': f"风险审计失败: {audit_result.get('error')}"
            }
        
        audit = audit_result['audit']
        
        # 4. 双专家决策
        blue = BlueAdvice(
            action=strategy.get('action', 'hold'),
            confidence=strategy.get('confidence', 0.5),
            reasoning=strategy.get('reasoning', ''),
            entry_price=strategy.get('entry_price'),
            stop_loss=strategy.get('stop_loss'),
            take_profit=strategy.get('take_profit')
        )
        
        red = RedAudit(
            risk_score=audit.get('risk_score', 5.0),
            critical_flaws=audit.get('critical_flaws', []),
            concerns=audit.get('concerns', []),
            recommendation=audit.get('recommendation', '')
        )
        
        decision = self.decision_engine.evaluate(blue, red)
        
        return {
            'symbol': symbol,
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'quote': context,
            'strategy': strategy,
            'audit': audit,
            'decision': {
                'action': decision.decision.value,
                'risk_level': decision.risk_level.value,
                'execution_allowed': decision.execution_allowed,
                'warning': decision.warning_message
            }
        }
    
    def analyze_batch(self, symbols: List[str]) -> Dict:
        """
        批量分析
        
        Args:
            symbols: 标的代码列表
            
        Returns:
            批量分析结果
        """
        results = []
        stats = {
            'total': len(symbols),
            'success': 0,
            'failed': 0,
            'approve': 0,
            'caution': 0,
            'reject': 0
        }
        
        print(f"\n📊 开始批量风控分析: {len(symbols)} 只标的")
        print("=" * 60)
        
        for symbol in symbols:
            result = self.analyze_symbol(symbol)
            results.append(result)
            
            if result['success']:
                stats['success'] += 1
                decision = result['decision']['action']
                if decision == 'approve':
                    stats['approve'] += 1
                elif decision == 'caution':
                    stats['caution'] += 1
                elif decision == 'reject':
                    stats['reject'] += 1
            else:
                stats['failed'] += 1
        
        return {
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'results': results
        }
    
    def generate_report(self, batch_result: Dict, format: str = 'text') -> str:
        """
        生成报告
        
        Args:
            batch_result: 批量分析结果
            format: 格式 (text/json/md)
            
        Returns:
            报告内容
        """
        if format == 'json':
            return json.dumps(batch_result, ensure_ascii=False, indent=2)
        
        elif format == 'md':
            lines = []
            lines.append("# 批量风控分析报告")
            lines.append(f"\n生成时间: {batch_result['timestamp']}")
            lines.append(f"\n## 统计")
            
            stats = batch_result['stats']
            lines.append(f"- 总标的: {stats['total']}")
            lines.append(f"- 成功: {stats['success']}")
            lines.append(f"- 失败: {stats['failed']}")
            lines.append(f"- 通过: {stats['approve']}")
            lines.append(f"- 谨慎: {stats['caution']}")
            lines.append(f"- 拒绝: {stats['reject']}")
            
            lines.append("\n## 详细结果")
            
            for result in batch_result['results']:
                if not result['success']:
                    lines.append(f"\n### {result['symbol']} ❌")
                    lines.append(f"错误: {result.get('error', '未知错误')}")
                    continue
                
                decision = result['decision']
                emoji = {'approve': '✅', 'caution': '⚠️', 'reject': '🛑'}.get(decision['action'], '⚪')
                
                lines.append(f"\n### {result['symbol']} {emoji}")
                lines.append(f"- 当前价: {result['quote']['price']:.3f} ({result['quote']['change_pct']:+.2f}%)")
                lines.append(f"- 蓝军建议: {result['strategy']['action'].upper()} (置信度{result['strategy']['confidence']:.0%})")
                lines.append(f"- 红军评分: {result['audit']['risk_score']:.1f}/10")
                lines.append(f"- 决策: {decision['warning']}")
            
            return "\n".join(lines)
        
        else:  # text
            lines = []
            lines.append("📊 批量风控分析报告")
            lines.append("=" * 60)
            lines.append(f"生成时间: {batch_result['timestamp']}")
            
            stats = batch_result['stats']
            lines.append(f"\n统计:")
            lines.append(f"  总标的: {stats['total']}")
            lines.append(f"  成功: {stats['success']}")
            lines.append(f"  失败: {stats['failed']}")
            lines.append(f"  通过: {stats['approve']} | 谨慎: {stats['caution']} | 拒绝: {stats['reject']}")
            
            lines.append("\n详细结果:")
            lines.append("-" * 60)
            
            for result in batch_result['results']:
                if not result['success']:
                    lines.append(f"\n{result['symbol']}: ❌ {result.get('error', '')}")
                    continue
                
                decision = result['decision']
                emoji = {'approve': '✅', 'caution': '⚠️', 'reject': '🛑'}.get(decision['action'], '⚪')
                
                lines.append(f"\n{result['symbol']} {emoji}")
                lines.append(f"  价格: {result['quote']['price']:.3f} ({result['quote']['change_pct']:+.2f}%)")
                lines.append(f"  蓝军: {result['strategy']['action'].upper()} ({result['strategy']['confidence']:.0%})")
                lines.append(f"  红军: {result['audit']['risk_score']:.1f}/10")
                lines.append(f"  决策: {decision['warning']}")
            
            return "\n".join(lines)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量风控分析工具")
    parser.add_argument("symbols", nargs="+", help="标的代码列表")
    parser.add_argument("--format", choices=['text', 'json', 'md'], default='text',
                       help="输出格式")
    parser.add_argument("--output", type=str, default=None,
                       help="输出文件路径")
    parser.add_argument("--watchlist", action="store_true",
                       help="分析自选股列表")
    
    args = parser.parse_args()
    
    # 确定要分析的标的
    symbols = args.symbols
    
    if args.watchlist:
        try:
            watchlist_path = Path("watchlist.json")
            with open(watchlist_path, 'r') as f:
                data = json.load(f)
                symbols = data.get('stocks', [])
            print(f"📋 加载自选股列表: {len(symbols)} 只")
        except Exception as e:
            print(f"❌ 加载自选股失败: {e}")
            return 1
    
    if not symbols:
        print("❌ 未指定标的")
        return 1
    
    # 执行分析
    analyzer = BatchRiskAnalyzer()
    result = analyzer.analyze_batch(symbols)
    
    # 生成报告
    report = analyzer.generate_report(result, format=args.format)
    
    # 输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✅ 报告已保存: {args.output}")
    else:
        print("\n" + report)
    
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sys.exit(main())
