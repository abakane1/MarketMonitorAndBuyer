# -*- coding: utf-8 -*-
"""
utils/strategy.py 的单元测试

测试覆盖:
- analyze_volume_profile_strategy() 核心逻辑
- 空数据处理
- 支撑位/阻力位识别
- 买入/卖出信号条件
- 仓位计算
"""
import pytest
import pandas as pd
from utils.strategy import analyze_volume_profile_strategy


class TestAnalyzeVolumeProfileStrategy:
    """测试 analyze_volume_profile_strategy 函数"""
    
    def test_empty_volume_profile_returns_nodata(self, empty_volume_profile):
        """空筹码分布应返回 NODATA 信号"""
        result = analyze_volume_profile_strategy(
            current_price=10.0,
            vol_profile=empty_volume_profile,
            total_capital=100000.0
        )
        assert result['signal'] == "NODATA"
    
    def test_zero_price_returns_nodata(self, sample_volume_profile):
        """价格为 0 应返回 NODATA 信号"""
        result = analyze_volume_profile_strategy(
            current_price=0,
            vol_profile=sample_volume_profile,
            total_capital=100000.0
        )
        assert result['signal'] == "NODATA"
    
    def test_buy_signal_near_support(self, sample_volume_profile):
        """价格接近支撑位时应产生买入信号"""
        # 支撑位在 9.5 (最高成交量节点低于当前价)
        # 价格 9.6，与 9.5 的差距 = (9.6-9.5)/9.6 ≈ 1.04%
        result = analyze_volume_profile_strategy(
            current_price=9.6,
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            proximity_threshold=0.03  # 3% 阈值
        )
        assert result['signal'] == "买入"
        assert result['support'] == 9.5
    
    def test_sell_signal_near_resistance(self, sample_volume_profile):
        """价格接近阻力位时应产生卖出信号（当有持仓时）"""
        # 阻力位在 10.5 (最高成交量节点高于当前价)
        # 价格 10.4，与 10.5 的差距 = (10.5-10.4)/10.4 ≈ 0.96%
        result = analyze_volume_profile_strategy(
            current_price=10.4,
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            current_shares=1000,  # 持有 1000 股
            proximity_threshold=0.03
        )
        assert result['signal'] == "卖出"
        assert result['resistance'] == 10.5
    
    def test_hold_signal_when_no_shares_near_resistance(self, sample_volume_profile):
        """无持仓时接近阻力位应产生观望信号"""
        result = analyze_volume_profile_strategy(
            current_price=10.4,
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            current_shares=0,  # 无持仓
            proximity_threshold=0.03
        )
        # 无持仓时卖出信号应转为观望
        assert result['signal'] == "观望"
    
    def test_wait_signal_in_middle_range(self, sample_volume_profile):
        """价格在支撑阻力中间时应产生观望信号"""
        result = analyze_volume_profile_strategy(
            current_price=10.0,  # 中间价格
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            proximity_threshold=0.02  # 2% 阈值
        )
        assert result['signal'] == "观望"
    
    def test_position_sizing_calculation(self, sample_volume_profile):
        """测试仓位计算逻辑"""
        result = analyze_volume_profile_strategy(
            current_price=9.6,
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            risk_per_trade=0.02,  # 2% 风险 = 2000 元
            current_shares=0,
            proximity_threshold=0.03
        )
        
        # 验证计算出的仓位合理性
        assert result['quantity'] >= 0
        assert result['target_position'] >= 0
        # 仓位应该是 100 的倍数 (A股规则)
        assert result['target_position'] % 100 == 0
    
    def test_no_negative_quantity_on_buy_signal(self, sample_volume_profile):
        """买入信号不应返回负数股数 (回归测试)"""
        # 场景: 当前持仓超过目标仓位时,买入信号不应建议卖出
        result = analyze_volume_profile_strategy(
            current_price=9.6,
            vol_profile=sample_volume_profile,
            total_capital=100000.0,
            risk_per_trade=0.02,
            current_shares=10000,  # 已持有大量股份
            proximity_threshold=0.03
        )
        
        # 买入信号下不应有负数量 (这是之前的 bug)
        assert result['quantity'] >= 0
        # 当仓位已满时应显示持股信号
        assert result['signal'] in ["买入", "持股"]


class TestSupportResistanceIdentification:
    """测试支撑阻力位识别逻辑"""
    
    def test_support_is_highest_volume_below_price(self, sample_volume_profile):
        """支撑位应为当前价格下方成交量最大的价位"""
        result = analyze_volume_profile_strategy(
            current_price=10.0,
            vol_profile=sample_volume_profile,
            total_capital=100000.0
        )
        # 10.0 下方: 9.0(5000), 9.5(15000) -> 支撑应为 9.5
        assert result['support'] == 9.5
    
    def test_resistance_is_highest_volume_above_price(self, sample_volume_profile):
        """阻力位应为当前价格上方成交量最大的价位"""
        result = analyze_volume_profile_strategy(
            current_price=10.0,
            vol_profile=sample_volume_profile,
            total_capital=100000.0
        )
        # 10.0 上方: 10.5(12000), 11.0(8000) -> 阻力应为 10.5
        assert result['resistance'] == 10.5
