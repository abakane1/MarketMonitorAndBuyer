#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4.1 功能集成测试

测试所有v4.1新模块的协同工作
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestV4_1_Database:
    """测试v4.1数据库结构"""
    
    def test_intelligence_table_columns(self):
        """测试intelligence表新增字段"""
        import sqlite3
        
        conn = sqlite3.connect("stock_data/intel_hub.db")
        cursor = conn.cursor()
        
        # 检查新增字段
        cursor.execute("PRAGMA table_info(intelligence)")
        columns = {row[1] for row in cursor.fetchall()}
        
        assert 'is_archived' in columns, "缺少is_archived字段"
        assert 'summary' in columns, "缺少summary字段"
        assert 'confidence' in columns, "缺少confidence字段"
        assert 'sentiment' in columns, "缺少sentiment字段"
        
        conn.close()
    
    def test_intelligence_stocks_table(self):
        """测试关联表存在"""
        import sqlite3
        
        conn = sqlite3.connect("stock_data/intel_hub.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intelligence_stocks'")
        assert cursor.fetchone() is not None, "intelligence_stocks表不存在"
        
        conn.close()
    
    def test_etf_keywords_table(self):
        """测试ETF配置表"""
        import sqlite3
        
        conn = sqlite3.connect("stock_data/intel_hub.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM etf_keywords")
        count = cursor.fetchone()[0]
        
        assert count >= 3, f"ETF配置数量不足: {count}"
        
        conn.close()


class TestV4_1_DataHealth:
    """测试数据源健康监控"""
    
    def test_health_monitor_import(self):
        """测试模块导入"""
        from utils.data_health_monitor import DataHealthMonitor
        assert DataHealthMonitor is not None
    
    def test_health_check(self):
        """测试健康检查功能"""
        from utils.data_health_monitor import DataHealthMonitor
        
        monitor = DataHealthMonitor()
        results = monitor.check_all_sources()
        
        # 至少应该有一个数据源
        assert len(results) > 0, "没有检查任何数据源"
        
        # 检查数据结构
        for name, record in results.items():
            assert hasattr(record, 'status'), f"{name}缺少status属性"
            assert hasattr(record, 'success_rate'), f"{name}缺少success_rate属性"


class TestV4_1_Intelligence:
    """测试情报系统"""
    
    def test_intel_analyzer_import(self):
        """测试分析器导入"""
        from scripts.intel_analyzer import IntelligenceAnalyzer
        assert IntelligenceAnalyzer is not None
    
    def test_intel_analyzer_load_etf(self):
        """测试ETF配置加载"""
        from scripts.intel_analyzer import IntelligenceAnalyzer
        
        analyzer = IntelligenceAnalyzer()
        
        # 应该有默认ETF配置
        assert len(analyzer.etf_configs) > 0, "没有加载ETF配置"
        
        # 检查特定ETF
        assert '588200' in analyzer.etf_configs, "缺少588200配置"
    
    def test_intel_archive_import(self):
        """测试归档模块导入"""
        from scripts.intel_archive import IntelligenceArchiver
        assert IntelligenceArchiver is not None


class TestV4_1_DualExpert:
    """测试双专家风控"""
    
    def test_decision_engine_import(self):
        """测试决策引擎导入"""
        from capability_platform.risk.dual_expert_decision import DualExpertDecisionEngine
        assert DualExpertDecisionEngine is not None
    
    def test_decision_matrix(self):
        """测试决策矩阵"""
        from capability_platform.risk.dual_expert_decision import (
            DualExpertDecisionEngine, BlueAdvice, RedAudit, Decision
        )
        
        engine = DualExpertDecisionEngine()
        
        # 测试场景: 低风险买入
        blue = BlueAdvice(action='buy', confidence=0.8, reasoning='test')
        red = RedAudit(risk_score=3.0, critical_flaws=[], concerns=[], recommendation='')
        
        result = engine.evaluate(blue, red)
        
        assert result.decision == Decision.APPROVE, "低风险应该通过"
        assert result.execution_allowed == True, "低风险应该允许执行"
        
        # 测试场景: 高风险买入
        red_high = RedAudit(risk_score=8.0, critical_flaws=[], concerns=[], recommendation='')
        result_high = engine.evaluate(blue, red_high)
        
        assert result_high.decision == Decision.REJECT, "高风险应该拒绝"
        assert result_high.execution_allowed == False, "高风险不应该允许执行"


class TestV4_1_AIInterface:
    """测试AI接口统一"""
    
    def test_ai_interface_import(self):
        """测试接口导入"""
        from utils.ai_interface import UnifiedAIInterface
        assert UnifiedAIInterface is not None
    
    def test_strategy_generator_import(self):
        """测试策略生成器导入"""
        from utils.ai_interface import StrategyGenerator
        assert StrategyGenerator is not None
    
    def test_risk_auditor_import(self):
        """测试风险审计器导入"""
        from utils.ai_interface import RiskAuditor
        assert RiskAuditor is not None


class TestV4_1_Backtest:
    """测试v4.2回测框架(v4.1基础上扩展)"""
    
    def test_backtest_engine_import(self):
        """测试回测引擎导入"""
        from capability_platform.backtest.engine import BacktestEngine
        assert BacktestEngine is not None
    
    def test_metrics_import(self):
        """测试指标模块导入"""
        from capability_platform.backtest.metrics import calculate_metrics
        assert calculate_metrics is not None


def run_all_tests():
    """运行所有测试"""
    print("🧪 运行v4.1集成测试")
    print("=" * 60)
    
    test_classes = [
        TestV4_1_Database,
        TestV4_1_DataHealth,
        TestV4_1_Intelligence,
        TestV4_1_DualExpert,
        TestV4_1_AIInterface,
        TestV4_1_Backtest
    ]
    
    results = []
    
    for test_class in test_classes:
        print(f"\n📋 测试类: {test_class.__name__}")
        print("-" * 40)
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                method()
                print(f"  ✅ {method_name}")
                results.append((test_class.__name__, method_name, True, None))
            except Exception as e:
                print(f"  ❌ {method_name}: {str(e)[:50]}")
                results.append((test_class.__name__, method_name, False, str(e)))
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("-" * 40)
    
    passed = sum(1 for _, _, success, _ in results if success)
    failed = sum(1 for _, _, success, _ in results if not success)
    
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  总计: {len(results)}")
    
    if failed > 0:
        print("\n❌ 失败详情:")
        for cls, method, success, error in results:
            if not success:
                print(f"  - {cls}.{method}: {error}")
    else:
        print("\n✅ 所有测试通过！")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
