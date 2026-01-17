from datetime import datetime, time

def is_trading_time() -> bool:
    """
    检查当前时间是否在 A 股交易时间内（包括集合竞价）。
    范围：09:15 - 11:30, 13:00 - 15:05 (仅限工作日)
    """
    now = datetime.now()
    
    # 1. 检查是否为周末 (周六=5, 周日=6)
    if now.weekday() > 4:
        return False
    
    current_time = now.time()
    
    # 定义交易时段
    morning_start = time(9, 15)
    morning_end = time(11, 30)
    
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 5) # 为收盘集合竞价预留 5 分钟缓冲
    
    # 检查上午时段
    is_morning = morning_start <= current_time <= morning_end
    
    # 检查下午时段
    is_afternoon = afternoon_start <= current_time <= afternoon_end
    
    return is_morning or is_afternoon
