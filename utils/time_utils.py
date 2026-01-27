from datetime import datetime, time, timedelta

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
    
    return is_trading_day(now.date()) and (is_morning or is_afternoon)

# 2026 Holiday Calendar (Simplified for Key Holidays)
# 1.1 New Year; 
# 2.17-2.24 Spring Festival (Sample dates, adjust as needed or use library)
# For this user request: Jan 24 is specified as Holiday/Weekend.
# Jan 24, 2026 is a Saturday. So weekday check covers it.
# But if it was a Friday holiday, we need this list.
HOLIDAYS_2026 = [
    "2026-01-01", 
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24", # Spring Festival
    "2026-04-04", # Tomb Sweeping
    "2026-05-01", "2026-05-02", "2026-05-03",
    "2026-06-22", # Dragon Boat
    "2026-09-27", # Mid Autumn
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07"
]

def is_trading_day(date_obj) -> bool:
    """
    Checks if a date is a valid trading day (Mon-Fri and not a holiday).
    """
    if date_obj.weekday() > 4: # Sat, Sun
        return False
    
    date_str = date_obj.strftime("%Y-%m-%d")
    if date_str in HOLIDAYS_2026:
        return False
        
    return True

def get_next_trading_day(start_date=None) -> datetime.date:
    """
    Returns the next valid trading day starting from start_date (exclusive).
    If start_date is None, uses Today.
    If today is Mon, next is Tue.
    If today is Fri, next is Mon.
    """
    if not start_date:
        start_date = datetime.now().date()
        
    next_day = start_date + timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)
    return next_day

def get_target_date_for_strategy(generated_time: datetime) -> str:
    """
    Determines the applicable trading date for a strategy generated at `generated_time`.
    Rule:
    - If generated BEFORE 15:00 on a Trading Day: Applies to TODAY.
    - If generated AFTER 15:00 on a Trading Day: Applies to NEXT Trading Day.
    - If generated on a Non-Trading Day: Applies to NEXT Trading Day.
    """
    date_obj = generated_time.date()
    is_today_trading = is_trading_day(date_obj)
    
    if is_today_trading:
        if generated_time.time() >= time(15, 0):
             # After Close -> Next Day
             target = get_next_trading_day(date_obj)
             return target.strftime("%Y-%m-%d")
        else:
             # Intelligent check: Before 09:00? Usually means Pre-market for TODAY.
             # Between 09:00 - 15:00? Intraday for TODAY.
             return date_obj.strftime("%Y-%m-%d")
    else:
        # Weekend/Holiday -> Next Trading Day
        target = get_next_trading_day(date_obj)
        return target.strftime("%Y-%m-%d")
