# batch_strategy.py
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import logging

from utils.queue_manager import StrategyQueue
# 导入你现有的策略生成模块
# from strategy_generator import generate_strategy_for_stock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BatchStrategyGenerator:
    """批量策略生成器"""
    
    def __init__(self, 
                 watchlist_file: str = "watchlist.json",
                 queue_file: str = "strategy_queue.json"):
        self.queue = StrategyQueue(queue_file)
        self.watchlist_file = watchlist_file
        self.running = False
        self.current_thread = None
        self.progress_callback: Optional[Callable] = None
        
    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def load_watchlist(self) -> List[Dict]:
        """加载关注的股票列表"""
        import json
        try:
            with open(self.watchlist_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # 默认关注列表
            return [
                {'code': '588710', 'name': '科创50ETF', 'priority': 1},
                # 添加你的5只股票
            ]
    
    def save_watchlist(self, watchlist: List[Dict]):
        """保存关注的股票列表"""
        import json
        with open(self.watchlist_file, 'w') as f:
            json.dump(watchlist, f, indent=2)
    
    def start_batch_generation(self, codes: List[str] = None, 
                               date: str = None) -> Dict:
        """
        启动批量生成
        
        Args:
            codes: 指定股票代码列表，None则使用全部关注列表
            date: 策略日期，None则使用明天
        """
        if self.running:
            return {'success': False, 'error': '已有批量任务在运行'}
        
        # 设置日期
        if date is None:
            tomorrow = datetime.now() + timedelta(days=1)
            date = tomorrow.strftime('%Y-%m-%d')
        
        # 获取股票列表
        if codes is None:
            watchlist = self.load_watchlist()
        else:
            watchlist = [{'code': c, 'name': '', 'priority': 0} for c in codes]
        
        # 添加到队列
        added = self.queue.add_watchlist(watchlist)
        
        if not added:
            return {'success': False, 'error': '没有新的股票需要生成'}
        
        # 启动后台线程
        self.running = True
        self.current_thread = threading.Thread(
            target=self._process_queue,
            args=(date,),
            daemon=True
        )
        self.current_thread.start()
        
        return {
            'success': True,
            'message': f'已添加 {len(added)} 只股票到队列',
            'codes': added,
            'date': date
        }
    
    def _process_queue(self, date: str):
        """处理队列（后台线程）"""
        logger.info(f"开始批量生成策略，日期: {date}")
        
        while self.running:
            item = self.queue.get_next()
            if not item:
                break
            
            code = item['code']
            logger.info(f"正在生成 {code} 的策略...")
            
            try:
                # 调用你的策略生成函数
                # result = generate_strategy_for_stock(code, date)
                
                # 模拟生成过程（替换为实际调用）
                result = self._mock_generate(code, date)
                
                # 保存结果
                self.queue.mark_completed(item['id'], result)
                
                # 发送进度通知
                if self.progress_callback:
                    self.progress_callback({
                        'type': 'completed',
                        'code': code,
                        'result': result,
                        'queue_status': self.queue.get_status()
                    })
                
                logger.info(f"{code} 策略生成完成")
                
            except Exception as e:
                logger.error(f"{code} 策略生成失败: {str(e)}")
                self.queue.mark_failed(item['id'], str(e))
                
                if self.progress_callback:
                    self.progress_callback({
                        'type': 'failed',
                        'code': code,
                        'error': str(e)
                    })
            
            # 短暂休息，避免请求过快
            time.sleep(2)
        
        self.running = False
        logger.info("批量生成完成")
        
        if self.progress_callback:
            self.progress_callback({
                'type': 'batch_completed',
                'queue_status': self.queue.get_status()
            })
    
    def _mock_generate(self, code: str, date: str) -> Dict:
        """模拟策略生成（替换为实际逻辑）"""
        # 这里调用你现有的策略生成代码
        # return generate_strategy(code, date)
        
        time.sleep(3)  # 模拟3秒生成时间
        
        return {
            'code': code,
            'date': date,
            'signal': 'HOLD',  # BUY, SELL, HOLD
            'confidence': 0.75,
            'reasoning': '基于技术分析和市场情绪...',
            'position': {'action': '保持', 'size': 100},
            'stop_loss': None,
            'take_profit': None
        }
    
    def stop_generation(self):
        """停止生成"""
        self.running = False
        return {'success': True, 'message': '已发送停止信号'}
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'running': self.running,
            'queue': self.queue.get_status()
        }
    
    def get_strategy_result(self, code: str, date: str = None) -> Optional[Dict]:
        """获取某只股票的策略结果"""
        for item in self.queue.queue:
            if item['code'] == code and item['status'] == 'completed':
                if date is None or item.get('result', {}).get('date') == date:
                    return item['result']
        return None


# 单例模式
_generator = None

def get_generator() -> BatchStrategyGenerator:
    """获取批量生成器实例"""
    global _generator
    if _generator is None:
        _generator = BatchStrategyGenerator()
    return _generator


if __name__ == '__main__':
    # 命令行测试
    gen = get_generator()
    
    # 打印当前关注列表
    watchlist = gen.load_watchlist()
    print(f"关注列表: {[w['code'] for w in watchlist]}")
    
    # 启动批量生成
    result = gen.start_batch_generation()
    print(result)
    
    # 等待完成
    try:
        while gen.running:
            status = gen.get_status()
            print(f"\r进度: {status['queue']}", end='')
            time.sleep(1)
    except KeyboardInterrupt:
        gen.stop_generation()
        print("\n已停止")
