# -*- coding: utf-8 -*-
"""
数据源健康监控模块 (Data Health Monitor)

v4.1.0 新增模块
功能:
1. 定期检查各数据源可用性
2. 记录数据源成功率
3. 自动告警通知
4. 为AI提供数据源选择建议

Author: AI Programmer
Date: 2026-03-14
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# 健康检查结果保存路径
HEALTH_LOG_PATH = Path("logs/data_health.json")


@dataclass
class DataSourceHealth:
    """单个数据源健康状态"""
    name: str                          # 数据源名称
    status: str                        # healthy/degraded/down
    success_rate: float               # 成功率 (0-1)
    avg_response_time: float          # 平均响应时间(ms)
    last_check: str                   # 最后检查时间 ISO格式
    last_success: Optional[str]       # 最后成功时间
    consecutive_failures: int         # 连续失败次数
    total_requests: int               # 总请求数
    total_success: int                # 成功数
    error_message: Optional[str]      # 错误信息


class DataHealthMonitor:
    """
    数据源健康监控器
    
    使用示例:
        monitor = DataHealthMonitor()
        monitor.check_all_sources()
        monitor.save_health_report()
    """
    
    def __init__(self, test_symbol: str = "588200"):
        self.test_symbol = test_symbol
        self.health_records: Dict[str, DataSourceHealth] = {}
        self._load_history()
    
    def _load_history(self):
        """加载历史健康记录"""
        if HEALTH_LOG_PATH.exists():
            try:
                with open(HEALTH_LOG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, record in data.get('sources', {}).items():
                        self.health_records[name] = DataSourceHealth(**record)
            except Exception as e:
                logger.warning(f"加载健康记录失败: {e}")
    
    def _save_history(self):
        """保存健康记录"""
        try:
            HEALTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'updated_at': datetime.now().isoformat(),
                'sources': {name: asdict(record) for name, record in self.health_records.items()}
            }
            with open(HEALTH_LOG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存健康记录失败: {e}")
    
    def check_sina_source(self) -> DataSourceHealth:
        """检查新浪数据源"""
        start_time = time.time()
        try:
            from utils.data_fallback import get_stock_spot_sina
            data = get_stock_spot_sina(self.test_symbol)
            response_time = (time.time() - start_time) * 1000
            
            if data and data.get('最新价', 0) > 0:
                return DataSourceHealth(
                    name="Sina Finance",
                    status="healthy",
                    success_rate=1.0,
                    avg_response_time=response_time,
                    last_check=datetime.now().isoformat(),
                    last_success=datetime.now().isoformat(),
                    consecutive_failures=0,
                    total_requests=1,
                    total_success=1,
                    error_message=None
                )
            else:
                raise ValueError("返回数据无效")
                
        except Exception as e:
            return DataSourceHealth(
                name="Sina Finance",
                status="down",
                success_rate=0.0,
                avg_response_time=(time.time() - start_time) * 1000,
                last_check=datetime.now().isoformat(),
                last_success=None,
                consecutive_failures=1,
                total_requests=1,
                total_success=0,
                error_message=str(e)
            )
    
    def check_tencent_source(self) -> DataSourceHealth:
        """检查腾讯数据源"""
        start_time = time.time()
        try:
            from utils.data_fallback import get_stock_spot_tencent
            data = get_stock_spot_tencent(self.test_symbol)
            response_time = (time.time() - start_time) * 1000
            
            if data and data.get('最新价', 0) > 0:
                return DataSourceHealth(
                    name="Tencent Finance",
                    status="healthy",
                    success_rate=1.0,
                    avg_response_time=response_time,
                    last_check=datetime.now().isoformat(),
                    last_success=datetime.now().isoformat(),
                    consecutive_failures=0,
                    total_requests=1,
                    total_success=1,
                    error_message=None
                )
            else:
                raise ValueError("返回数据无效")
                
        except Exception as e:
            return DataSourceHealth(
                name="Tencent Finance",
                status="down",
                success_rate=0.0,
                avg_response_time=(time.time() - start_time) * 1000,
                last_check=datetime.now().isoformat(),
                last_success=None,
                consecutive_failures=1,
                total_requests=1,
                total_success=0,
                error_message=str(e)
            )
    
    def check_akshare_source(self) -> DataSourceHealth:
        """检查akshare数据源(东方财富)"""
        start_time = time.time()
        try:
            import akshare as ak
            # 使用简单的接口测试
            df = ak.stock_zh_a_spot_em()
            response_time = (time.time() - start_time) * 1000
            
            if df is not None and not df.empty:
                return DataSourceHealth(
                    name="AKShare (EastMoney)",
                    status="healthy",
                    success_rate=1.0,
                    avg_response_time=response_time,
                    last_check=datetime.now().isoformat(),
                    last_success=datetime.now().isoformat(),
                    consecutive_failures=0,
                    total_requests=1,
                    total_success=1,
                    error_message=None
                )
            else:
                raise ValueError("返回数据为空")
                
        except Exception as e:
            return DataSourceHealth(
                name="AKShare (EastMoney)",
                status="down",
                success_rate=0.0,
                avg_response_time=(time.time() - start_time) * 1000,
                last_check=datetime.now().isoformat(),
                last_success=None,
                consecutive_failures=1,
                total_requests=1,
                total_success=0,
                error_message=str(e)[:100]
            )
    
    def check_all_sources(self) -> Dict[str, DataSourceHealth]:
        """检查所有数据源"""
        logger.info("开始检查数据源健康状态...")
        
        self.health_records["Sina Finance"] = self.check_sina_source()
        self.health_records["Tencent Finance"] = self.check_tencent_source()
        self.health_records["AKShare (EastMoney)"] = self.check_akshare_source()
        
        self._save_history()
        return self.health_records
    
    def get_best_source(self) -> Optional[str]:
        """
        获取当前最佳数据源
        AI可以根据这个建议自动选择数据源
        """
        healthy_sources = [
            name for name, record in self.health_records.items()
            if record.status == "healthy"
        ]
        
        if not healthy_sources:
            return None
        
        # 优先顺序: Sina > Tencent > AKShare
        priority = ["Sina Finance", "Tencent Finance", "AKShare (EastMoney)"]
        for source in priority:
            if source in healthy_sources:
                return source
        
        return healthy_sources[0]
    
    def generate_report(self) -> str:
        """生成健康检查报告"""
        lines = ["📊 数据源健康检查报告", "=" * 50, ""]
        
        for name, record in self.health_records.items():
            status_emoji = "🟢" if record.status == "healthy" else "🔴"
            lines.append(f"{status_emoji} {name}")
            lines.append(f"   状态: {record.status}")
            lines.append(f"   成功率: {record.success_rate*100:.1f}%")
            lines.append(f"   响应时间: {record.avg_response_time:.0f}ms")
            lines.append(f"   最后检查: {record.last_check[:19]}")
            if record.error_message:
                lines.append(f"   错误: {record.error_message}")
            lines.append("")
        
        best = self.get_best_source()
        lines.append(f"✨ 推荐数据源: {best or '无可用数据源'}")
        
        return "\n".join(lines)
    
    def should_alert(self) -> Tuple[bool, str]:
        """判断是否需要告警"""
        down_sources = [
            name for name, record in self.health_records.items()
            if record.status != "healthy"
        ]
        
        if len(down_sources) == len(self.health_records):
            return True, f"🚨 严重: 所有数据源不可用!"
        
        if down_sources:
            return True, f"⚠️ 警告: 以下数据源异常: {', '.join(down_sources)}"
        
        return False, ""


def run_health_check():
    """运行健康检查 (供命令行使用)"""
    monitor = DataHealthMonitor()
    monitor.check_all_sources()
    print(monitor.generate_report())
    
    should_alert, alert_msg = monitor.should_alert()
    if should_alert:
        print(f"\n{alert_msg}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_health_check())
