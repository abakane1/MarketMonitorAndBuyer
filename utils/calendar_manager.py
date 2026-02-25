from datetime import datetime, timedelta, date
import logging
import pandas as pd
import akshare as ak
from utils.database import (
    db_save_trade_date, db_get_single_trade_date, 
    db_get_trade_dates_range, db_get_future_trade_dates
)

# Use standard logging as monitor_logger doesn't export get_logger
logger = logging.getLogger("calendar_mgr")

class CalendarManager:
    """
    Manages A-Share trading calendar using local DB and AkShare synchronization.
    """
    
    def sync_calendar_from_akshare(year: str = None):
        """
        Fetches official holiday/trading data from Sina via AkShare and updates DB.
        If year is None, syncs current year.
        """
        if not year:
            year = str(datetime.now().year)
            
        logger.info(f"Syncing trading calendar for {year}...")
        
        try:
            # tool_trade_date_hist_sina returns a DF with `trade_date` column
            df = ak.tool_trade_date_hist_sina()
            
            # Filter for requested year (and maybe next year to be safe)
            # The API returns ALL history, so we need to filter.
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
            
            # Filter range: Start of Year to End of Year
            start_date = date(int(year), 1, 1)
            end_date = date(int(year), 12, 31)
            
            # Get valid trading dates
            trading_dates = set(df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]['trade_date'])
            
            # Iterate through all days in the year to populate DB (including holidays)
            current = start_date
            count = 0
            while current <= end_date:
                d_str = current.strftime("%Y-%m-%d")
                is_trading = 1 if current in trading_dates else 0
                
                # Determine description (Simple logic: Weekend vs Weekday non-trading)
                is_weekend = current.weekday() > 4
                is_holiday = 0
                desc = ""
                
                if not is_trading:
                    if is_weekend:
                        desc = "Weekend"
                    else:
                        is_holiday = 1
                        desc = "Holiday (Official)"
                
                db_save_trade_date(d_str, is_trading, is_holiday, desc)
                current += timedelta(days=1)
                count += 1
                
            logger.info(f"Calendar sync complete. Processed {count} days.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync calendar: {e}")
            return False

    @staticmethod
    def is_trading_day(target_date: date) -> bool:
        """
        Checks if date is a trading day.
        1. Query DB.
        2. If DB missing, fallback to basic logic (Mon-Fri) + Warning.
        """
        d_str = target_date.strftime("%Y-%m-%d")
        record = db_get_single_trade_date(d_str)
        
        if record:
            return record['is_trading']
        
        # Fallback
        # logger.warning(f"Calendar DB miss for {d_str}, using fallback logic.")
        return target_date.weekday() < 5

    @staticmethod
    def get_next_trading_day(start_date: date) -> date:
        """
        Finds the next trading day > start_date.
        """
        # Try DB first
        # Look ahead 30 days
        s_str = (start_date + timedelta(days=1)).strftime("%Y-%m-%d")
        future_dates = db_get_future_trade_dates(s_str, limit=5)
        
        if future_dates:
            return datetime.strptime(future_dates[0], "%Y-%m-%d").date()
            
        # Fallback loop
        next_day = start_date + timedelta(days=1)
        while next_day.weekday() > 4: # Skip weekend
            next_day += timedelta(days=1)
        return next_day

    @staticmethod
    def get_upcoming_holidays(limit: int = 5) -> list:
        """
        Returns upcoming non-weekend holidays.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Need custom query for this, or just scan
        # For efficiency, we just assume this is rare op.
        # TODO: Implement if needed for UI.
        return []
