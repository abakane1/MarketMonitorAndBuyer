from datetime import datetime, time

def is_trading_time() -> bool:
    """
    Checks if current time is within A-share trading hours (including Call Auction).
    Range: 09:15 - 11:30, 13:00 - 15:05 (Weekdays only)
    """
    now = datetime.now()
    
    # 1. Check Weekend (Saturday=5, Sunday=6)
    if now.weekday() > 4:
        return False
    
    current_time = now.time()
    
    # Define Slots
    morning_start = time(9, 15)
    morning_end = time(11, 30)
    
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 5) # Allow 5 mins buffer for closing call
    
    # Check Morning
    is_morning = morning_start <= current_time <= morning_end
    
    # Check Afternoon
    is_afternoon = afternoon_start <= current_time <= afternoon_end
    
    return is_morning or is_afternoon
