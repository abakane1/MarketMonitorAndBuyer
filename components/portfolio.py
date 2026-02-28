# -*- coding: utf-8 -*-
"""
操盘记录与盈亏面板 (Portfolio P&L Dashboard)
v3.0.0 新增组件
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from utils.database import (
    db_get_all_positions,
    db_get_all_history,
    db_compute_realized_pnl,
    db_get_watchlist,
    db_get_trade_dates_range # Added
)
from utils.data_fetcher import get_stock_realtime_info
from utils.asset_classifier import is_etf # Added


def _get_stock_name(symbol: str) -> str:
    """尝试获取股票名称，失败则返回代码本身。"""
    try:
        info = get_stock_realtime_info(symbol)
        if info and info.get('name'):
            return info['name']
    except:
        pass
    return symbol


def _render_overview_metrics(positions: list, all_pnl_data: dict):
    """
    渲染总览卡片区域。
    positions: db_get_all_positions() 返回的列表
    all_pnl_data: {symbol: db_compute_realized_pnl() 返回的 dict}
    """
    # 计算汇总指标
    total_market_value = 0.0
    total_cost_value = 0.0
    total_realized_pnl = 0.0
    total_today_pnl = 0.0
    
    for pos in positions:
        symbol = pos["symbol"]
        shares = pos["shares"]
        cost = pos["cost"]
        
        # 获取最新价
        info = get_stock_realtime_info(symbol)
        current_price = float(info.get('price', 0)) if info else 0
        pre_close = float(info.get('pre_close', current_price)) if info else current_price
        
        market_value = shares * current_price
        cost_value = shares * cost
        
        total_market_value += market_value
        total_cost_value += cost_value
        
        # 今日盈亏 = (当前价 - 昨收) * 持仓量
        today_pnl = (current_price - pre_close) * shares
        total_today_pnl += today_pnl
    
    # 累计已实现盈亏
    for symbol, pnl_data in all_pnl_data.items():
        total_realized_pnl += pnl_data.get("realized_pnl", 0)
    
    # 浮动盈亏
    floating_pnl = total_market_value - total_cost_value
    floating_pct = (floating_pnl / total_cost_value * 100) if total_cost_value > 0 else 0
    
    # 总盈亏 = 已实现 + 浮动
    total_pnl = total_realized_pnl + floating_pnl
    
    # 渲染4列卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 总持仓市值",
            value=f"¥{total_market_value:,.0f}",
            help="所有持仓股票的当前市值总和"
        )
    
    with col2:
        delta_color = "normal" if floating_pnl >= 0 else "inverse"
        st.metric(
            label="📊 浮动盈亏",
            value=f"¥{floating_pnl:+,.0f}",
            delta=f"{floating_pct:+.2f}%",
            delta_color=delta_color,
            help="当前市值与持仓成本的差额"
        )
    
    with col3:
        today_color = "normal" if total_today_pnl >= 0 else "inverse"
        st.metric(
            label="📅 今日盈亏",
            value=f"¥{total_today_pnl:+,.0f}",
            delta_color=today_color,
            help="今日价格变动导致的持仓盈亏"
        )
    
    with col4:
        realized_color = "normal" if total_realized_pnl >= 0 else "inverse"
        st.metric(
            label="✅ 累计已实现",
            value=f"¥{total_realized_pnl:+,.0f}",
            delta_color=realized_color,
            help="所有卖出操作累计的已实现盈亏（移动平均成本法）"
        )
    
    # 总盈亏汇总条
    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
    st.markdown(
        f"<div style='text-align:center; padding:8px; "
        f"background:{'rgba(0,200,83,0.1)' if total_pnl >= 0 else 'rgba(255,82,82,0.1)'}; "
        f"border-radius:8px; margin:8px 0;'>"
        f"<span style='font-size:1.1em;'>{pnl_emoji} <b>总盈亏 (已实现+浮动)</b>: "
        f"<span style='color:{'#00c853' if total_pnl >= 0 else '#ff5252'}; font-size:1.3em;'>"
        f"¥{total_pnl:+,.0f}</span></span></div>",
        unsafe_allow_html=True
    )


def _render_position_table(positions: list, all_pnl_data: dict):
    """渲染个股持仓明细表。"""
    if not positions:
        st.info("📭 当前无持仓")
        return
    
    etf_rows = []
    stock_rows = []
    
    for pos in positions:
        symbol = pos["symbol"]
        shares = pos["shares"]
        cost = pos["cost"]
        base = pos.get("base_shares", 0)
        
        # 获取实时数据
        info = get_stock_realtime_info(symbol)
        name = _get_stock_name(symbol) if not info else info.get('name', symbol)
        current_price = float(info.get('price', 0)) if info else 0
        
        market_value = shares * current_price
        cost_value = shares * cost
        floating_pnl = market_value - cost_value
        floating_pct = (floating_pnl / cost_value * 100) if cost_value > 0 else 0
        
        # 已实现盈亏
        pnl_data = all_pnl_data.get(symbol, {})
        realized = pnl_data.get("realized_pnl", 0)
        
        row_data = {
            "股票": f"{name} ({symbol})",
            "持仓": shares,
            "底仓": base,
            "成本价": round(cost, 3),
            "最新价": current_price,
            "市值": round(market_value, 0),
            "浮动盈亏": round(floating_pnl, 0),
            "盈亏%": round(floating_pct, 2),
            "已实现": round(realized, 0)
        }
        
        if is_etf(symbol):
            etf_rows.append(row_data)
        else:
            stock_rows.append(row_data)
    
    # 使用 Streamlit 的条件格式
    def color_pnl(val):
        """为盈亏列上色。"""
        if isinstance(val, (int, float)):
            if val > 0:
                return "color: #00c853; font-weight: bold;"
            elif val < 0:
                return "color: #ff5252; font-weight: bold;"
        return ""
    
    def render_dataframe(title, subtitle, r_list, bg_color):
        if not r_list:
            return
        st.markdown(f"<h4 style='margin-bottom: 0px;'>{title}</h4>", unsafe_allow_html=True)
        st.markdown(f"<span style='color: gray; font-size: 0.9em;'>{subtitle}</span>", unsafe_allow_html=True)
        
        df = pd.DataFrame(r_list)
        styled = df.style.applymap(color_pnl, subset=["浮动盈亏", "盈亏%", "已实现"])
        
        # 设置行样式和格式化
        styled = styled.set_table_styles([
            {'selector': 'thead th', 'props': [('background-color', bg_color)]}
        ])
        
        styled = styled.format({
            "成本价": "{:.3f}",
            "最新价": "{:.2f}",
            "市值": "¥{:,.0f}",
            "浮动盈亏": "¥{:+,.0f}",
            "盈亏%": "{:+.2f}%",
            "已实现": "¥{:+,.0f}"
        })
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.write("") # break
        
    render_dataframe(
        "🛡️ 长线护城河 (ETF 底仓)", 
        "策略：网格/定投、越跌越买、钝化短线破位、耐心积累份额。",
        etf_rows,
        "rgba(33, 150, 243, 0.2)"
    )
    
    render_dataframe(
        "⚔️ 短线突击队 (个股)", 
        "策略：动量突破、右侧追高、严格止损、高抛低吸。",
        stock_rows,
        "rgba(255, 152, 0, 0.2)"
    )


def _render_pnl_chart(all_pnl_data: dict, positions: list):
    """渲染累计收益曲线。"""
    # 合并所有股票的日盈亏数据
    combined_daily = {}
    
    for symbol, pnl_data in all_pnl_data.items():
        for day in pnl_data.get("daily_pnl", []):
            date = day["date"]
            if date not in combined_daily:
                combined_daily[date] = 0.0
            combined_daily[date] += day["pnl"]
    
    if not combined_daily:
        st.info("📈 暂无历史卖出记录，无法生成收益曲线。开始交易后数据将自动充填。")
        return
    
    # 引入日期和交易日历
    import datetime
    from utils.database import db_get_trade_dates_range
    
    # 获取日期范围
    min_date = min(combined_daily.keys())
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    max_date = max(max(combined_daily.keys()), today_str)
    
    # 从数据库获取交易日历
    td_info = db_get_trade_dates_range(min_date, max_date)
    trading_days = [d["date"] for d in td_info if d["is_trading"]]
    
    # 兼容处理：如果日历未初始化，降级生成工作日
    if not trading_days:
        curr = datetime.datetime.strptime(min_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(max_date, "%Y-%m-%d")
        while curr <= end:
            if curr.isoweekday() <= 5:
                trading_days.append(curr.strftime("%Y-%m-%d"))
            curr += datetime.timedelta(days=1)
            
    # 防止存在周末记录的交易漏掉，合并键值集合
    all_dates_set = set(trading_days) | set(combined_daily.keys())
    sorted_dates = sorted(list(all_dates_set))
    
    # 计算累计
    cumulative = []
    daily_values = []
    cum = 0.0
    for d in sorted_dates:
        pnl = combined_daily.get(d, 0.0)
        cum += pnl
        cumulative.append(cum)
        daily_values.append(pnl)
    
    # 创建 Plotly 图表
    fig = go.Figure()
    
    # 累计收益线
    fig.add_trace(go.Scatter(
        x=sorted_dates,
        y=cumulative,
        mode='lines+markers',
        name='累计已实现盈亏',
        line=dict(color='#2196f3', width=3),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(33, 150, 243, 0.1)'
    ))
    
    # 每日盈亏柱状图
    colors = ['#00c853' if v >= 0 else '#ff5252' for v in daily_values]
    fig.add_trace(go.Bar(
        x=sorted_dates,
        y=daily_values,
        name='每日已实现盈亏',
        marker_color=colors,
        opacity=0.6,
        yaxis='y2'
    ))
    
    fig.update_layout(
        title=dict(text="📈 累计收益曲线 (P&L Curve)", font=dict(size=16)),
        xaxis_title="交易日期",
        xaxis=dict(type='category', tickangle=-45), # 强制类目轴，忽略日历断层
        yaxis=dict(title="累计盈亏 (¥)", side='left'),
        yaxis2=dict(title="每日盈亏 (¥)", side='right', overlaying='y'),
        template="plotly_dark",
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    # 零线
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    st.plotly_chart(fig, use_container_width=True)


def _render_transaction_log(limit: int = 50):
    """渲染交易流水。"""
    all_history = db_get_all_history()
    
    if not all_history:
        st.info("📝 暂无交易记录")
        return
    
    # 限制显示数量
    display_list = all_history[:limit]
    
    rows = []
    for tx in display_list:
        t = str(tx["type"]).strip().lower()
        
        # 确定操作类型图标
        if any(w in t for w in ["买", "入", "buy"]):
            action = "🟢 买入"
            action_color = "#00c853"
        elif any(w in t for w in ["卖", "出", "sell"]):
            action = "🔴 卖出"
            action_color = "#ff5252"
        elif "override" in t or "修正" in t:
            action = "🔧 修正"
            action_color = "#ff9800"
        else:
            action = f"❓ {tx['type']}"
            action_color = "#999"
        
        name = _get_stock_name(tx["symbol"])
        amount = float(tx.get("price", 0)) * float(tx.get("amount", 0))
        
        rows.append({
            "时间": tx["timestamp"],
            "操作": action,
            "股票": f"{name} ({tx['symbol']})",
            "价格": tx["price"],
            "数量": int(tx["amount"]),
            "金额": round(amount, 0),
            "备注": tx.get("note", "")
        })
    
    df = pd.DataFrame(rows)
    
    def color_action(val):
        """为操作列上色。"""
        if "买入" in str(val):
            return "color: #00c853;"
        elif "卖出" in str(val):
            return "color: #ff5252;"
        elif "修正" in str(val):
            return "color: #ff9800;"
        return ""
    
    styled = df.style.applymap(color_action, subset=["操作"])
    styled = styled.format({
        "价格": "{:.3f}",
        "金额": "¥{:,.0f}"
    })
    
    st.dataframe(styled, use_container_width=True, hide_index=True)
    
    if len(all_history) > limit:
        st.caption(f"仅显示最近 {limit} 条记录（共 {len(all_history)} 条）")


def render_portfolio_dashboard():
    """
    渲染操盘记录与盈亏面板主入口。
    """
    st.header("💼 操盘记录 (Portfolio P&L)")
    st.caption("基于交易流水，使用移动平均成本法计算盈亏。数据实时更新。")
    
    # 获取所有持仓
    positions = db_get_all_positions()
    
    # 获取关注列表中所有股票（包括已清仓的）的盈亏数据
    watchlist = db_get_watchlist()
    all_symbols = set([p["symbol"] for p in positions] + watchlist)
    
    # 计算每只股票的已实现盈亏
    all_pnl_data = {}
    for symbol in all_symbols:
        pnl = db_compute_realized_pnl(symbol)
        if pnl["trade_count"] > 0:
            all_pnl_data[symbol] = pnl
    
    # === 模块 1: 总览卡片 ===
    _render_overview_metrics(positions, all_pnl_data)
    
    st.markdown("---")
    
    # === 模块 2 + 3 + 4: 使用 Tabs 组织 ===
    tab1, tab2, tab3 = st.tabs(["📊 持仓明细", "📈 收益曲线", "📋 交易流水"])
    
    with tab1:
        _render_position_table(positions, all_pnl_data)
        
        # 汇总统计
        if all_pnl_data:
            st.markdown("---")
            st.subheader("📊 交易统计概览")
            
            total_trades = sum(p.get("trade_count", 0) for p in all_pnl_data.values())
            total_buy = sum(p.get("total_buy_amount", 0) for p in all_pnl_data.values())
            total_sell = sum(p.get("total_sell_amount", 0) for p in all_pnl_data.values())
            
            c1, c2, c3 = st.columns(3)
            c1.metric("总交易次数", f"{total_trades} 笔")
            c2.metric("累计买入金额", f"¥{total_buy:,.0f}")
            c3.metric("累计卖出金额", f"¥{total_sell:,.0f}")
    
    with tab2:
        _render_pnl_chart(all_pnl_data, positions)
    
    with tab3:
        _render_transaction_log()
