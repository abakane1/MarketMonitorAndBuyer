# -*- coding: utf-8 -*-
"""
Pytest 配置文件
设置项目根路径和共享 fixtures
"""
import sys
import os
import pytest
import pandas as pd

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def sample_volume_profile():
    """
    提供测试用的筹码分布数据
    """
    return pd.DataFrame({
        'price_bin': [9.0, 9.5, 10.0, 10.5, 11.0],
        '成交量': [5000, 15000, 3000, 12000, 8000]  # 9.5 和 10.5 是高成交量节点
    })


@pytest.fixture
def empty_volume_profile():
    """
    空的筹码分布数据
    """
    return pd.DataFrame(columns=['price_bin', '成交量'])


@pytest.fixture
def sample_minute_data():
    """
    提供测试用的分时数据
    """
    times = pd.date_range('2026-01-19 09:30', periods=10, freq='1min')
    return pd.DataFrame({
        '时间': times,
        '开盘': [10.0, 10.1, 10.2, 10.15, 10.1, 10.05, 10.0, 10.1, 10.2, 10.25],
        '收盘': [10.1, 10.2, 10.15, 10.1, 10.05, 10.0, 10.1, 10.2, 10.25, 10.3],
        '最高': [10.15, 10.25, 10.22, 10.18, 10.12, 10.08, 10.15, 10.25, 10.28, 10.35],
        '最低': [9.98, 10.08, 10.12, 10.08, 10.02, 9.98, 9.98, 10.08, 10.18, 10.22],
        '成交量': [1000, 1200, 800, 900, 1500, 2000, 1100, 900, 1300, 1600]
    })
