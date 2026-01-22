# -*- coding: utf-8 -*-
"""
utils/data_fetcher.py 的单元测试

测试覆盖:
- get_price_precision() 精度判断
- analyze_intraday_pattern() 分时分析
- aggregate_minute_to_daily() 聚合逻辑
"""
import pytest
import pandas as pd
from utils.data_fetcher import get_price_precision, analyze_intraday_pattern, aggregate_minute_to_daily


class TestGetPricePrecision:
    """测试 get_price_precision 函数"""
    
    def test_etf_588_returns_3_decimals(self):
        """588 开头的 ETF 应返回 3 位小数"""
        assert get_price_precision("588000") == 3
        assert get_price_precision("588080") == 3
    
    def test_etf_51_returns_3_decimals(self):
        """51 开头的 ETF 应返回 3 位小数"""
        assert get_price_precision("510050") == 3
        assert get_price_precision("510300") == 3
    
    def test_etf_15_returns_3_decimals(self):
        """15 开头的 ETF 应返回 3 位小数"""
        assert get_price_precision("159915") == 3
        assert get_price_precision("159919") == 3
    
    def test_stock_returns_2_decimals(self):
        """普通股票应返回 2 位小数"""
        assert get_price_precision("600519") == 2  # 茅台
        assert get_price_precision("000001") == 2  # 平安银行
        assert get_price_precision("300750") == 2  # 宁德时代


class TestAnalyzeIntradayPattern:
    """测试 analyze_intraday_pattern 函数"""
    
    def test_empty_dataframe_returns_no_data(self):
        """空 DataFrame 应返回无数据提示"""
        result = analyze_intraday_pattern(pd.DataFrame())
        assert "无分时数据" in result
    
    def test_insufficient_data_returns_warning(self):
        """数据不足时应返回警告"""
        df = pd.DataFrame({
            '时间': pd.date_range('2026-01-19 09:30', periods=5, freq='1min'),
            '收盘': [10.0, 10.1, 10.2, 10.15, 10.1],
            '成交量': [1000, 1200, 800, 900, 1500]
        })
        result = analyze_intraday_pattern(df)
        assert "数据不足" in result
    
    def test_valid_data_returns_summary(self, sample_minute_data):
        """有效数据应返回分析摘要"""
        result = analyze_intraday_pattern(sample_minute_data)
        # 应包含趋势描述
        assert any(keyword in result for keyword in ["上行", "下行", "震荡"])
    
    def test_upward_trend_detected(self, sample_minute_data):
        """应检测到上涨趋势"""
        # sample_minute_data 收盘价从 10.1 涨到 10.3
        result = analyze_intraday_pattern(sample_minute_data)
        assert "上行" in result or "上攻" in result


class TestAggregateMinuteToDaily:
    """测试 aggregate_minute_to_daily 函数"""
    
    def test_empty_dataframe_returns_na(self):
        """空 DataFrame 应返回 N/A"""
        result = aggregate_minute_to_daily(pd.DataFrame())
        assert result == "N/A"
    
    def test_missing_time_column_returns_na(self):
        """缺少时间列应返回 N/A"""
        df = pd.DataFrame({'收盘': [10.0, 10.1], '成交量': [1000, 1200]})
        result = aggregate_minute_to_daily(df)
        assert "N/A" in result
    
    def test_valid_data_returns_formatted_string(self, sample_minute_data):
        """有效数据应返回格式化的日线摘要"""
        result = aggregate_minute_to_daily(sample_minute_data, precision=2)
        # 应包含日期和 OHLCV 信息
        assert "2026-01-19" in result
        assert "O=" in result  # Open
        assert "H=" in result  # High
        assert "L=" in result  # Low
        assert "C=" in result  # Close
        assert "V=" in result  # Volume
    
    def test_precision_affects_formatting(self, sample_minute_data):
        """精度参数应影响格式化结果"""
        result_2 = aggregate_minute_to_daily(sample_minute_data, precision=2)
        result_3 = aggregate_minute_to_daily(sample_minute_data, precision=3)
        # 不同精度应产生不同格式
        assert result_2 != result_3


class TestDataFetcherErrorHandling:
    """测试数据获取的错误处理"""
    
    def test_market_code_identification(self):
        """测试市场代码识别"""
        from utils.data_fetcher import _get_market_code
        
        # 上海: 6*, 9*
        assert _get_market_code("600519") == "sh"
        assert _get_market_code("688001") == "sh"
        
        # 深圳: 0*, 3*
        assert _get_market_code("000001") == "sz"
        assert _get_market_code("300750") == "sz"
        
        # 北京: 4*, 8*
        assert _get_market_code("430047") == "bj"
        assert _get_market_code("830839") == "bj"
