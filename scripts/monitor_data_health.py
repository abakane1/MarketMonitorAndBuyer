#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源健康监控脚本

Usage:
    python scripts/monitor_data_health.py
    
功能:
    - 每分钟检查数据源健康状态
    - 异常时发送告警
    - 记录健康历史

v4.1.0 新增
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_health_monitor import run_health_check

if __name__ == "__main__":
    exit_code = run_health_check()
    sys.exit(exit_code)
