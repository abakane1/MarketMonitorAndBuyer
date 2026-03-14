#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场离线快照模块 (Market Snapshot)

v4.1.0 Week 2 - Data Fallback Protocol Phase 2
功能:
1. 每日收盘后保存全市场列表
2. 保存ETF净值、溢价率数据
3. 极端情况下提供静态查询能力

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_fallback import get_stock_spot_sina, get_stock_spot_tencent

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("stock_data/snapshots")


class MarketSnapshot:
    """市场快照管理器"""
    
    def __init__(self):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_snapshot_path(self, date: Optional[str] = None) -> Path:
        """获取快照文件路径"""
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        return SNAPSHOT_DIR / f"market_snapshot_{date}.json"
    
    def capture_spot_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        捕获指定标的的实时数据
        
        Args:
            symbols: 标的代码列表
            
        Returns:
            标的数据字典
        """
        data = {}
        
        for symbol in symbols:
            try:
                # 优先使用Sina
                spot = get_stock_spot_sina(symbol)
                if not spot:
                    # 失败时使用Tencent
                    spot = get_stock_spot_tencent(symbol)
                
                if spot:
                    data[symbol] = {
                        'name': spot.get('名称', ''),
                        'price': spot.get('最新价', 0),
                        'pre_close': spot.get('昨收', 0),
                        'open': spot.get('今开', 0),
                        'high': spot.get('最高', 0),
                        'low': spot.get('最低', 0),
                        'volume': spot.get('成交量', 0),
                        'amount': spot.get('成交额', 0),
                        'change_pct': spot.get('涨跌幅', 0),
                        'timestamp': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"获取 {symbol} 数据失败: {e}")
        
        return data
    
    def save_snapshot(self, data: Dict, date: Optional[str] = None) -> bool:
        """
        保存快照
        
        Args:
            data: 快照数据
            date: 日期(YYYYMMDD)
            
        Returns:
            是否成功
        """
        try:
            snapshot_path = self._get_snapshot_path(date)
            
            snapshot = {
                'date': date or datetime.now().strftime('%Y%m%d'),
                'created_at': datetime.now().isoformat(),
                'data': data,
                'count': len(data)
            }
            
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
            logger.info(f"快照已保存: {snapshot_path} ({len(data)} 条)")
            return True
            
        except Exception as e:
            logger.error(f"保存快照失败: {e}")
            return False
    
    def load_snapshot(self, date: Optional[str] = None) -> Optional[Dict]:
        """
        加载快照
        
        Args:
            date: 日期(YYYYMMDD)，None表示最新
            
        Returns:
            快照数据
        """
        try:
            if date:
                snapshot_path = self._get_snapshot_path(date)
            else:
                # 获取最新的快照
                snapshots = sorted(SNAPSHOT_DIR.glob("market_snapshot_*.json"))
                if not snapshots:
                    return None
                snapshot_path = snapshots[-1]
            
            if not snapshot_path.exists():
                return None
            
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"加载快照失败: {e}")
            return None
    
    def get_cached_spot(self, symbol: str) -> Optional[Dict]:
        """
        从缓存获取标的实时数据
        
        Args:
            symbol: 标的代码
            
        Returns:
            标的数据
        """
        snapshot = self.load_snapshot()
        if not snapshot:
            return None
        
        return snapshot.get('data', {}).get(symbol)
    
    def list_snapshots(self) -> List[Dict]:
        """列出所有快照"""
        snapshots = []
        
        for path in sorted(SNAPSHOT_DIR.glob("market_snapshot_*.json")):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    snapshots.append({
                        'date': data.get('date'),
                        'count': data.get('count', 0),
                        'created_at': data.get('created_at'),
                        'path': str(path)
                    })
            except Exception:
                pass
        
        return snapshots
    
    def cleanup_old_snapshots(self, keep_days: int = 30):
        """
        清理旧快照
        
        Args:
            keep_days: 保留天数
        """
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        for path in SNAPSHOT_DIR.glob("market_snapshot_*.json"):
            try:
                # 从文件名提取日期
                date_str = path.stem.split('_')[-1]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if file_date < cutoff:
                    path.unlink()
                    logger.info(f"已删除旧快照: {path}")
            except Exception:
                pass


def create_watchlist_snapshot():
    """为自选股列表创建快照"""
    try:
        # 加载自选股
        watchlist_path = Path("watchlist.json")
        if not watchlist_path.exists():
            print("❌ 自选股列表不存在")
            return False
        
        with open(watchlist_path, 'r') as f:
            watchlist = json.load(f)
        
        symbols = watchlist.get('stocks', [])
        if not symbols:
            print("❌ 自选股列表为空")
            return False
        
        print(f"📝 为 {len(symbols)} 只自选股创建快照...")
        
        snapshot_mgr = MarketSnapshot()
        data = snapshot_mgr.capture_spot_data(symbols)
        
        if snapshot_mgr.save_snapshot(data):
            print(f"✅ 快照创建成功 ({len(data)} 条)")
            return True
        else:
            print("❌ 快照创建失败")
            return False
            
    except Exception as e:
        logger.error(f"创建自选股快照失败: {e}")
        return False


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="市场快照工具")
    parser.add_argument("--capture", action="store_true",
                       help="创建自选股快照")
    parser.add_argument("--list", action="store_true",
                       help="列出所有快照")
    parser.add_argument("--show", type=str, metavar="SYMBOL",
                       help="显示指定标的的最新缓存数据")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", default=None,
                       help="清理指定天数前的快照")
    
    args = parser.parse_args()
    
    if args.capture:
        create_watchlist_snapshot()
    
    elif args.list:
        mgr = MarketSnapshot()
        snapshots = mgr.list_snapshots()
        
        if not snapshots:
            print("📂 没有快照")
        else:
            print("📂 快照列表")
            print("-" * 60)
            for s in snapshots:
                print(f"  {s['date']}: {s['count']} 条标的")
                print(f"    创建时间: {s['created_at'][:19]}")
    
    elif args.show:
        mgr = MarketSnapshot()
        data = mgr.get_cached_spot(args.show)
        
        if data:
            print(f"📊 {args.show} ({data['name']})")
            print(f"  价格: {data['price']}")
            print(f"  昨收: {data['pre_close']}")
            print(f"  涨跌: {data['change_pct']:.2f}%")
            print(f"  快照时间: {data['timestamp'][:19]}")
        else:
            print(f"❌ 未找到 {args.show} 的缓存数据")
    
    elif args.cleanup:
        mgr = MarketSnapshot()
        mgr.cleanup_old_snapshots(keep_days=args.cleanup)
        print(f"✅ 已清理 {args.cleanup} 天前的快照")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
