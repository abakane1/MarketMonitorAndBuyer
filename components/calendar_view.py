import streamlit as st
from datetime import datetime, date, timedelta
from utils.calendar_manager import CalendarManager
from utils.database import db_get_trade_dates_range

def render_calendar_view():
    """
    Renders the Trading Calendar management page.
    """
    st.header("📅 交易日历管理 (Trading Calendar)")
    
    # --- Action Bar ---
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 同步官方日历", type="primary", use_container_width=True):
            with st.spinner("正在从 AkShare 同步日历..."):
                success = CalendarManager.sync_calendar_from_akshare()
                if success:
                    st.success("同步成功！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("同步失败，请检查日志。")
    
    with col2:
        st.info("从 AkShare (Sina源) 同步官方交易日/节假日数据。每日只需同步一次。")
        
    st.markdown("---")
    
    # --- Calendar Visualization ---
    # Show current month by default
    today = datetime.now().date()
    
    # Controls
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        view_year = st.number_input("年份", min_value=2024, max_value=2030, value=today.year)
    with c_col2:
        view_month = st.selectbox("月份", range(1, 13), index=today.month - 1)
        
    # Get Data for selected Month
    import calendar
    import time
    
    _, num_days = calendar.monthrange(view_year, view_month)
    start_date = date(view_year, view_month, 1)
    end_date = date(view_year, view_month, num_days)
    
    dates_data = db_get_trade_dates_range(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    
    # Transform to map for O(1) lookup
    date_map = {d["date"]: d for d in dates_data}
    
    # Grid Layout
    st.subheader(f"{view_year}年 {view_month}月")
    
    # Weekday Headers
    cols = st.columns(7)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i, w in enumerate(weekdays):
        cols[i].markdown(f"**{w}**")
        
    # Fill empty days before 1st of month
    first_weekday = start_date.weekday() # 0=Mon
    
    # Create week rows
    current_day = 1
    
    # Row 1
    cols = st.columns(7)
    for i in range(7):
        if i < first_weekday:
            cols[i].write("")
        else:
            d_obj = date(view_year, view_month, current_day)
            d_str = d_obj.strftime("%Y-%m-%d")
            
            # Render Day
            _render_day_cell(cols[i], d_str, date_map.get(d_str), d_obj == today)
            current_day += 1
            
    # Subsequent Rows
    while current_day <= num_days:
        cols = st.columns(7)
        for i in range(7):
            if current_day > num_days:
                cols[i].write("")
            else:
                d_obj = date(view_year, view_month, current_day)
                d_str = d_obj.strftime("%Y-%m-%d")
                _render_day_cell(cols[i], d_str, date_map.get(d_str), d_obj == today)
                current_day += 1
    
    # --- Upcoming Holidays ---
    st.markdown("---")
    st.subheader("🏖️ 近期节假日")
    # Simple query for holidays
    # In a real app we'd query DB where is_holiday=1 from now. 
    # For now just showing a placeholder or simple logic
    st.caption("显示未来30天内的非周末节假日：")
    
    # (Optional: Add query logic here if strictly required, else skip for MVP)


def _render_day_cell(ui_col, date_str, data, is_today):
    """Helper to render a single day cell"""
    day_num = int(date_str.split("-")[2])
    
    # Style
    bg_color = "transparent"
    border = "1px solid #eee"
    
    status_emoji = "❓" # Unknown
    is_trading = False
    
    if data:
        if data["is_trading"]:
            status_emoji = "🟢" # Trading
            is_trading = True
        elif data.get("is_holiday"):
            status_emoji = "🔴" # Holiday
            bg_color = "#ffeeee"
        else:
            status_emoji = "💤" # Weekend/Closed
            bg_color = "#f9f9f9"
            
    if is_today:
        border = "2px solid #4CAF50"
    
    # HTML Content
    desc_text = data['description'] if data and data.get('description') else ''
    # 防止 description 中的 HTML 标签破坏布局
    desc_text = str(desc_text).replace('<', '&lt;').replace('>', '&gt;') if desc_text else ''
    
    html = f"""<div style="border: {border}; background-color: {bg_color}; padding: 5px; border-radius: 5px; min-height: 80px; text-align: center;">
    <div style="font-weight: bold; font-size: 1.1em;">{day_num}</div>
    <div style="font-size: 1.2em; margin-top: 5px;">{status_emoji}</div>
    <div style="font-size: 0.8em; color: #666;">{desc_text}</div>
</div>"""
    ui_col.markdown(html, unsafe_allow_html=True)
