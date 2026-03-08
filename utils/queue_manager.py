import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional
import os

class StrategyQueue:
    """策略生成队列管理器"""
    
    def __init__(self, queue_file: str = "strategy_queue.json"):
        self.queue_file = queue_file
        self.lock = threading.Lock()
        self._load_queue()
        
    def _load_queue(self):
        """加载队列状态"""
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r') as f:
                self.queue = json.load(f)
        else:
            self.queue = []
    
    def _save_queue(self):
        """保存队列状态"""
        with self.lock:
            with open(self.queue_file, 'w') as f:
                json.dump(self.queue, f, indent=2)
    
    def add_stock(self, code: str, name: str = "", priority: int = 0):
        """添加股票到队列"""
        item = {
            'id': f"{code}_{int(time.time())}",
            'code': code,
            'name': name,
            'status': 'pending',  # pending, running, completed, failed
            'priority': priority,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None
        }
        with self.lock:
            # 检查是否已在队列中
            if not any(q['code'] == code and q['status'] in ['pending', 'running'] for q in self.queue):
                self.queue.append(item)
                self._save_queue()
                return True
        return False
    
    def add_watchlist(self, codes: List[Dict]):
        """批量添加关注的股票"""
        added = []
        for stock in codes:
            if self.add_stock(stock['code'], stock.get('name', '')):
                added.append(stock['code'])
        return added
    
    def get_next(self) -> Optional[Dict]:
        """获取下一个待处理的股票"""
        with self.lock:
            pending = [q for q in self.queue if q['status'] == 'pending']
            if pending:
                # 按优先级排序
                pending.sort(key=lambda x: x['priority'], reverse=True)
                next_item = pending[0]
                next_item['status'] = 'running'
                next_item['started_at'] = datetime.now().isoformat()
                self._save_queue()
                return next_item
        return None
    
    def mark_completed(self, item_id: str, result: Dict):
        """标记为已完成"""
        with self.lock:
            for item in self.queue:
                if item['id'] == item_id:
                    item['status'] = 'completed'
                    item['completed_at'] = datetime.now().isoformat()
                    item['result'] = result
                    self._save_queue()
                    return True
        return False
    
    def mark_failed(self, item_id: str, error: str):
        """标记为失败"""
        with self.lock:
            for item in self.queue:
                if item['id'] == item_id:
                    item['status'] = 'failed'
                    item['completed_at'] = datetime.now().isoformat()
                    item['error'] = error
                    self._save_queue()
                    return True
        return False
    
    def get_status(self) -> Dict:
        """获取队列整体状态"""
        return {
            'total': len(self.queue),
            'pending': len([q for q in self.queue if q['status'] == 'pending']),
            'running': len([q for q in self.queue if q['status'] == 'running']),
            'completed': len([q for q in self.queue if q['status'] == 'completed']),
            'failed': len([q for q in self.queue if q['status'] == 'failed']),
            'items': self.queue[-10:]  # 最近10条
        }
    
    def clear_completed(self):
        """清理已完成的记录"""
        with self.lock:
            self.queue = [q for q in self.queue if q['status'] in ['pending', 'running']]
            self._save_queue()
