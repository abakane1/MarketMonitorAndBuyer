# -*- coding: utf-8 -*-
"""
操盘记录与盈亏面板 - 科技感大屏版 (Portfolio Trading Dashboard)
v3.2.0 - Cyberpunk/Sci-Fi Style
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from collections import defaultdict

from utils.database import (
    db_get_all_positions,
    db_get_all_history,
    db_compute_realized_pnl,
    db_get_watchlist,
)
from utils.data_fetcher import get_stock_realtime_info
from utils.asset_classifier import is_etf


# =============================================================================
# 清爽浅色主题 CSS 样式 - 适配20-30寸大屏
# =============================================================================
LIGHT_THEME_CSS = """
<style>
/* 全局背景 - 清爽浅灰 */
[data-testid="stAppViewContainer"] {
    background: #f8f9fa !important;
}

/* Main content area */
[data-testid="stMain"] {
    background: #f8f9fa !important;
}

/* Block container */
[data-testid="stBlock"] {
    background: transparent !important;
}

/* Vertical block */
[data-testid="stVerticalBlock"] {
    background: transparent !important;
}

/* 修复所有可能的深色背景 */
section.main {
    background: #f8f9fa !important;
}

/* 数据表格背景 */
[data-testid="stDataFrame"] {
    background: #ffffff !important;
}
[data-testid="stDataEditor"] {
    background: #ffffff !important;
}

/* Streamlit Tabs 背景色修复 */
[data-testid="stTabs"] {
    background: transparent !important;
}
[data-testid="stTab"] {
    background: #ffffff !important;
    color: #5f6368 !important;
    border-radius: 8px 8px 0 0 !important;
}
[data-testid="stTab"][aria-selected="true"] {
    background: #1a73e8 !important;
    color: #ffffff !important;
}
[data-baseweb="tab-list"] {
    background: #f8f9fa !important;
    border-bottom: 1px solid #e9ecef !important;
}
[data-baseweb="tab"] {
    background: transparent !important;
}
[data-baseweb="tab-panel"] {
    background: transparent !important;
}

/* 主容器 - 白色卡片 */
.cyber-container {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 12px;
    padding: 24px;
    margin: 12px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

/* 标题样式 - 深蓝色 */
.cyber-title {
    color: #1a73e8;
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 18px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e8f0fe;
}

/* 数据卡片 - 白色背景，蓝边 */
.metric-card {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
}

.metric-card:hover {
    border-color: #1a73e8;
    box-shadow: 0 4px 12px rgba(26,115,232,0.1);
}

.metric-value {
    font-size: 2rem;
    font-weight: 600;
    color: #202124;
}

.metric-value.positive {
    color: #137333;
}

.metric-value.negative {
    color: #c5221f;
}

.metric-label {
    color: #5f6368;
    font-size: 0.9rem;
    margin-top: 10px;
    font-weight: 500;
}

/* 持仓卡片 - 白色背景 */
.position-card {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-left: 4px solid #1a73e8;
    border-radius: 10px;
    padding: 20px;
    margin: 12px 0;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
}

.position-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.position-card.etf {
    border-left-color: #9334e6;
}

.position-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.position-symbol {
    font-size: 1.2rem;
    font-weight: 600;
    color: #202124;
}

.position-name {
    color: #5f6368;
    font-size: 0.9rem;
}

.position-pnl {
    font-size: 1.15rem;
    font-weight: 600;
}

.position-pnl.positive {
    color: #137333;
}

.position-pnl.negative {
    color: #c5221f;
}

/* 交易流水 - 白色背景 */
.trade-item {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 8px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-left: 4px solid transparent;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: all 0.15s ease;
}

.trade-item:hover {
    box-shadow: 0 3px 8px rgba(0,0,0,0.08);
}

.trade-item.buy {
    border-left-color: #137333;
    background: linear-gradient(90deg, rgba(19,115,51,0.03) 0%, #ffffff 100%);
}

.trade-item.sell {
    border-left-color: #c5221f;
    background: linear-gradient(90deg, rgba(197,34,31,0.03) 0%, #ffffff 100%);
}

.trade-time {
    color: #5f6368;
    font-size: 0.85rem;
}

.trade-symbol {
    color: #202124;
    font-weight: 500;
}

.trade-action {
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
}

.trade-action.buy {
    background: #e6f4ea;
    color: #137333;
}

.trade-action.sell {
    background: #fce8e6;
    color: #c5221f;
}

.trade-amount {
    color: #202124;
    font-weight: 600;
}

/* 标签 */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 14px;
    font-size: 0.75rem;
    font-weight: 600;
}

.badge-etf {
    background: #f3e8fd;
    color: #9334e6;
}

.badge-stock {
    background: #e8f0fe;
    color: #1a73e8;
}

/* 分割线 */
.cyber-divider {
    height: 1px;
    background: #dadce0;
    margin: 24px 0;
}

/* 状态指示器 */
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-dot.online {
    background: #137333;
}

/* 响应式字体调整 - 适配大屏 */
@media screen and (min-width: 1920px) {
    .metric-value {
        font-size: 2.2rem;
    }
    .position-symbol {
        font-size: 1.3rem;
    }
    .cyber-title {
        font-size: 1.35rem;
    }
}
</style>
"""


def _get_stock_name(symbol: str) -> str:
    """尝试获取股票名称，失败则返回代码本身。"""
    try:
        from utils.data_fetcher import get_stock_name_by_code_cached
        name = get_stock_name_by_code_cached(symbol)
        if name and name != symbol:
            return name
    except:
        pass
    
    try:
        info = get_stock_realtime_info(symbol)
        if info:
            name = info.get('name', '')
            if name and name not in ('Unknown', 'unknown', '', symbol):
                return name
    except:
        pass
    
    return symbol


def _calculate_portfolio_metrics(positions: list, all_pnl_data: dict, current_portfolio: str = "default"):
    """计算组合指标。"""
    metrics = {
        'total_market_value': 0.0,
        'total_cost_value': 0.0,
        'total_realized_pnl': 0.0,
        'total_today_pnl': 0.0,
        'position_count': len(positions),
        'etf_count': 0,
        'stock_count': 0,
    }
    
    position_details = []
    
    for pos in positions:
        symbol = pos["symbol"]
        shares = pos["shares"]
        cost = pos["cost"]
        base = pos.get("base_shares", 0)
        
        info = get_stock_realtime_info(symbol)
        name = _get_stock_name(symbol) if not info else info.get('name', symbol)
        current_price = float(info.get('price', 0)) if info else 0
        pre_close = float(info.get('pre_close', current_price)) if info else current_price
        
        market_value = shares * current_price
        cost_value = shares * cost
        floating_pnl = market_value - cost_value
        floating_pct = (floating_pnl / cost_value * 100) if cost_value > 0 else 0
        today_pnl = (current_price - pre_close) * shares
        
        pnl_data = all_pnl_data.get(symbol, {})
        realized = pnl_data.get("realized_pnl", 0)
        
        metrics['total_market_value'] += market_value
        metrics['total_cost_value'] += cost_value
        metrics['total_today_pnl'] += today_pnl
        
        if is_etf(symbol):
            metrics['etf_count'] += 1
            pos_type = 'ETF'
        else:
            metrics['stock_count'] += 1
            pos_type = '股票'
        
        position_details.append({
            'symbol': symbol,
            'name': name,
            'type': pos_type,
            'is_etf': is_etf(symbol),
            'shares': shares,
            'base_shares': base,
            'cost': cost,
            'price': current_price,
            'pre_close': pre_close,
            'market_value': market_value,
            'floating_pnl': floating_pnl,
            'floating_pct': floating_pct,
            'today_pnl': today_pnl,
            'realized_pnl': realized,
        })
    
    for pnl_data in all_pnl_data.values():
        metrics['total_realized_pnl'] += pnl_data.get("realized_pnl", 0)
    
    metrics['floating_pnl'] = metrics['total_market_value'] - metrics['total_cost_value']
    metrics['total_pnl'] = metrics['total_realized_pnl'] + metrics['floating_pnl']
    metrics['floating_pct'] = (metrics['floating_pnl'] / metrics['total_cost_value'] * 100) if metrics['total_cost_value'] > 0 else 0
    
    return metrics, position_details


def _render_cyber_metrics(metrics: dict):
    """渲染指标卡片。"""
    cols = st.columns(4)
    
    # 总持仓市值
    with cols[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">¥{metrics['total_market_value']:,.0f}</div>
            <div class="metric-label">总持仓市值</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 浮动盈亏
    pnl_class = "positive" if metrics['floating_pnl'] >= 0 else "negative"
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value {pnl_class}">{metrics['floating_pnl']:+,.0f}</div>
            <div class="metric-label">浮动盈亏 ({metrics['floating_pct']:+.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 今日盈亏
    today_class = "positive" if metrics['total_today_pnl'] >= 0 else "negative"
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value {today_class}">{metrics['total_today_pnl']:+,.0f}</div>
            <div class="metric-label">今日盈亏</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 累计已实现
    realized_class = "positive" if metrics['total_realized_pnl'] >= 0 else "negative"
    with cols[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value {realized_class}">{metrics['total_realized_pnl']:+,.0f}</div>
            <div class="metric-label">累计已实现</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 总盈亏汇总
    total_class = "positive" if metrics['total_pnl'] >= 0 else "negative"
    total_color = "#137333" if metrics['total_pnl'] >= 0 else "#c5221f"
    st.markdown(f"""
    <div style="
        background: #ffffff;
        border: 2px solid {total_color};
        border-radius: 10px;
        padding: 16px;
        margin: 16px 0;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    ">
        <div style="color: #5f6368; font-size: 0.85rem; margin-bottom: 6px;">总盈亏 (已实现 + 浮动)</div>
        <div style="color: {total_color}; font-size: 2rem; font-weight: 600;">
            ¥{metrics['total_pnl']:+,.0f}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_position_cards(position_details: list):
    """渲染持仓卡片网格。"""
    if not position_details:
        st.info("当前无持仓")
        return
    
    # 分离 ETF 和股票
    etf_positions = [p for p in position_details if p['is_etf']]
    stock_positions = [p for p in position_details if not p['is_etf']]
    
    # ETF 区域
    if etf_positions:
        st.markdown("<div class='cyber-title'>ETF底仓</div>", unsafe_allow_html=True)
        
        # 创建网格布局
        cols = st.columns(min(len(etf_positions), 3))
        for idx, pos in enumerate(etf_positions):
            with cols[idx % 3]:
                pnl_class = "positive" if pos['floating_pnl'] >= 0 else "negative"
                card_class = "position-card etf"
                
                st.markdown(f"""
                <div class="{card_class}">
                    <div class="position-header">
                        <div>
                            <div class="position-symbol">{pos['symbol']}</div>
                            <div class="position-name">{pos['name']}</div>
                        </div>
                        <span class="badge badge-etf">ETF</span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">持仓 / 底仓</div>
                            <div style="color: #202124;">{pos['shares']} / {pos['base_shares']}</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">成本 → 现价</div>
                            <div style="color: #202124;">{pos['cost']:.3f} → {pos['price']:.3f}</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">市值</div>
                            <div style="color: #202124;">¥{pos['market_value']:,.0f}</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">浮动盈亏</div>
                            <div class="position-pnl {pnl_class}">{pos['floating_pnl']:+,.0f} ({pos['floating_pct']:+.1f}%)</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # 股票区域
    if stock_positions:
        if etf_positions:
            st.markdown("<div class='cyber-divider'></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='cyber-title'>股票持仓</div>", unsafe_allow_html=True)
        
        cols = st.columns(min(len(stock_positions), 3))
        for idx, pos in enumerate(stock_positions):
            with cols[idx % 3]:
                pnl_class = "positive" if pos['floating_pnl'] >= 0 else "negative"
                today_class = "positive" if pos['today_pnl'] >= 0 else "negative"
                
                st.markdown(f"""
                <div class="position-card">
                    <div class="position-header">
                        <div>
                            <div class="position-symbol">{pos['symbol']}</div>
                            <div class="position-name">{pos['name']}</div>
                        </div>
                        <span class="badge badge-stock">股票</span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">持仓</div>
                            <div style="color: #202124;">{pos['shares']} 股</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">成本 → 现价</div>
                            <div style="color: #202124;">{pos['cost']:.3f} → {pos['price']:.3f}</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">今日盈亏</div>
                            <div style="color: {'#137333' if pos['today_pnl'] >= 0 else '#c5221f'};">{pos['today_pnl']:+,.0f}</div>
                        </div>
                        <div>
                            <div style="color: #5f6368; font-size: 0.75rem;">浮动盈亏</div>
                            <div class="position-pnl {pnl_class}">{pos['floating_pnl']:+,.0f}</div>
                        </div>
                    </div>
                    {f'<div style="margin-top: 8px; color: #b06000; font-size: 0.75rem;">底仓锁定: {pos["base_shares"]} 股</div>' if pos['base_shares'] > 0 else ''}
                </div>
                """, unsafe_allow_html=True)


def _render_pnl_chart(all_pnl_data: dict):
    """渲染科技感收益曲线。"""
    combined_daily = defaultdict(float)
    
    for pnl_data in all_pnl_data.values():
        for day in pnl_data.get("daily_pnl", []):
            combined_daily[day["date"]] += day["pnl"]
    
    if not combined_daily:
        st.info("📈 暂无历史交易记录")
        return
    
    sorted_dates = sorted(combined_daily.keys())
    cumulative = []
    daily_values = []
    cum = 0.0
    
    for d in sorted_dates:
        pnl = combined_daily[d]
        cum += pnl
        cumulative.append(cum)
        daily_values.append(pnl)
    
    # 创建图表
    fig = go.Figure()
    
    # 累计收益曲线
    fig.add_trace(go.Scatter(
        x=sorted_dates,
        y=cumulative,
        mode='lines',
        name='累计盈亏',
        line=dict(color='#1a73e8', width=2),
        fill='tozeroy',
        fillcolor='rgba(88, 166, 255, 0.1)',
    ))
    
    # 每日盈亏柱状图
    colors = ['#137333' if v >= 0 else '#c5221f' for v in daily_values]
    fig.add_trace(go.Bar(
        x=sorted_dates,
        y=daily_values,
        name='每日盈亏',
        marker_color=colors,
        opacity=0.6,
        yaxis='y2'
    ))
    
    fig.update_layout(
        template='plotly_white',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#202124'),
        title=dict(
            text='收益曲线',
            font=dict(size=16, color='#1a73e8'),
            x=0.5
        ),
        xaxis=dict(
            title='日期',
            gridcolor='rgba(0,0,0,0.1)',
            showgrid=True,
        ),
        yaxis=dict(
            title='累计盈亏',
            gridcolor='rgba(0,0,0,0.1)',
            showgrid=True,
            side='left'
        ),
        yaxis2=dict(
            title='每日盈亏',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            font=dict(color='#5f6368')
        ),
        margin=dict(l=60, r=60, t=80, b=60),
        height=450,
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    
    st.plotly_chart(fig, use_container_width=True)


def _render_trade_timeline(limit: int = 30, current_portfolio: str = "default"):
    """渲染交易流水。"""
    all_history = db_get_all_history()
    
    if not all_history:
        st.info("暂无交易记录")
        return
    
    # 过滤修正类交易
    trade_history = []
    for tx in all_history:
        t = str(tx.get("type", "")).strip().lower()
        # 剔除修正/override类数据
        if any(w in t for w in ["修正", "override", "覆盖", "调整", "update", "adjust", "modify"]):
            continue
        trade_history.append(tx)
    
    if not trade_history:
        st.info("暂无交易记录")
        return
    
    display_list = trade_history[:limit]
    
    st.markdown(f"<div class='cyber-title'>最近交易记录</div>", unsafe_allow_html=True)
    
    for tx in display_list:
        t = str(tx.get("type", "")).strip().lower()
        
        if any(w in t for w in ["买", "入", "buy"]):
            action_class = "buy"
            action_text = "买入"
        elif any(w in t for w in ["卖", "出", "sell"]):
            action_class = "sell"
            action_text = "卖出"
        else:
            continue  # 跳过其他类型
        
        name = _get_stock_name(tx["symbol"])
        price = float(tx.get("price", 0) or 0)
        amount = int(tx.get("amount", 0) or 0)
        total = price * amount
        
        st.markdown(f"""
        <div class="trade-item {action_class}">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div class="trade-action {action_class}">{action_text}</div>
                <div>
                    <div class="trade-symbol">{name} ({tx['symbol']})</div>
                    <div class="trade-time">{tx.get('timestamp', '')}</div>
                </div>
            </div>
            <div style="text-align: right;">
                <div class="trade-amount">¥{total:,.0f}</div>
                <div style="color: #5f6368; font-size: 0.75rem;">{price:.3f} × {amount}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    if len(trade_history) > limit:
        st.caption(f"共 {len(trade_history)} 条记录，显示最近 {limit} 条")


def _render_portfolio_stats(all_pnl_data: dict, metrics: dict):
    """渲染组合统计信息。"""
    if not all_pnl_data:
        return
    
    st.markdown("<div class='cyber-title'>交易统计</div>", unsafe_allow_html=True)
    
    total_trades = sum(p.get("trade_count", 0) for p in all_pnl_data.values())
    total_buy = sum(p.get("total_buy_amount", 0) for p in all_pnl_data.values())
    total_sell = sum(p.get("total_sell_amount", 0) for p in all_pnl_data.values())
    
    cols = st.columns(4)
    
    stats = [
        ("总交易次数", f"{total_trades} 笔", "#1a73e8"),
        ("累计买入", f"¥{total_buy:,.0f}", "#a371f7"),
        ("累计卖出", f"¥{total_sell:,.0f}", "#b06000"),
        ("持仓标的", f"{metrics['position_count']} 只", "#137333"),
    ]
    
    for col, (label, value, color) in zip(cols, stats):
        with col:
            st.markdown(f"""
            <div style="
                background: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                border: 1px solid {color}30;
            ">
                <div style="color: {color}; font-size: 1.2rem; font-weight: 600;">{value}</div>
                <div style="color: #5f6368; font-size: 0.8rem; margin-top: 5px;">{label}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_kline_with_trades():
    """渲染带有交易点位标注的行情 K 线图"""
    st.markdown("<div class='cyber-title'>个股交易标绘 (K线图)</div>", unsafe_allow_html=True)
    
    # 1. 选择要查看的股票
    positions = db_get_all_positions()
    watchlist = db_get_watchlist()
    all_symbols = list(set([p["symbol"] for p in positions] + watchlist))
    
    if not all_symbols:
        st.info("暂无持仓或自选股数据可供查看")
        return
        
    symbol_options = {sym: f"{_get_stock_name(sym)} ({sym})" for sym in all_symbols}
    
    col1, _ = st.columns([1, 2])
    with col1:
        selected_symbol = st.selectbox(
            "选择标的", 
            options=all_symbols, 
            format_func=lambda x: symbol_options.get(x, x),
            key="kline_symbol_selector"
        )
        
    if not selected_symbol:
        return
        
    # 2. 获取该股票的日线数据和交易历史
    from utils.data_fetcher import get_stock_daily_history
    
    with st.spinner(f"正在加载 {selected_symbol} 的历史行情..."):
        daily_df = get_stock_daily_history(selected_symbol, days=90)
        
    if daily_df.empty:
        st.warning(f"无法获取 {selected_symbol} 的近期 K 线数据。")
        return
        
    # 抽取交易记录
    all_history = db_get_all_history()
    stock_trades = [tx for tx in all_history if tx.get("symbol") == selected_symbol and str(tx.get("type", "")).strip().lower() in ["buy", "买入", "sell", "卖出"]]
    
    # 3. 绘制 Plotly K线图
    fig = go.Figure(data=[go.Candlestick(
        x=daily_df['日期'],
        open=daily_df['开盘'],
        high=daily_df['最高'],
        low=daily_df['最低'],
        close=daily_df['收盘'],
        name='K线',
        increasing_line_color='#c5221f', 
        decreasing_line_color='#137333'  
    )])
    
    # 添加交易点位作为 Scatter markers
    if stock_trades:
        buy_dates, buy_prices, buy_texts = [], [], []
        sell_dates, sell_prices, sell_texts = [], [], []
        
        for tx in stock_trades:
            # tx['timestamp'] format is usually 'YYYY-MM-DD HH:MM:SS'
            dt_str = str(tx.get('timestamp', '')).split(' ')[0]
            action = str(tx.get('type')).lower()
            price = tx.get('price', 0)
            amount = tx.get('amount', 0)
            text_label = f"{action.upper()} {amount}股 @ ¥{price}"
            
            # Simple date matching: find closest trading day if exact match is not in df
            if action in ['buy', '买入']:
                buy_dates.append(dt_str)
                buy_prices.append(price)
                buy_texts.append(text_label)
            else:
                sell_dates.append(dt_str)
                sell_prices.append(price)
                sell_texts.append(text_label)
                
        # 添加买入标记
        if buy_dates:
            fig.add_trace(go.Scatter(
                x=buy_dates, y=buy_prices,
                mode='markers',
                name='买入点 (Buy)',
                marker=dict(symbol='triangle-up', size=12, color='#c5221f', line=dict(width=1, color='White')),
                text=buy_texts,
                hoverinfo='text+x+y',
                yaxis='y'
            ))
            
        # 添加卖出标记
        if sell_dates:
            fig.add_trace(go.Scatter(
                x=sell_dates, y=sell_prices,
                mode='markers',
                name='卖出点 (Sell)',
                marker=dict(symbol='triangle-down', size=12, color='#137333', line=dict(width=1, color='White')),
                text=sell_texts,
                hoverinfo='text+x+y',
                yaxis='y'
            ))
            
    fig.update_layout(
        template='plotly_white',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#202124'),
        title=dict(text=f'{symbol_options.get(selected_symbol)} - 近90日 K线与交易点位', font=dict(color='#1a73e8')),
        xaxis=dict(title='', gridcolor='rgba(0,0,0,0.1)', rangeslider=dict(visible=False)),
        yaxis=dict(title='价格', gridcolor='rgba(0,0,0,0.1)'),
        margin=dict(l=60, r=60, t=60, b=40),
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_portfolio_dashboard():
    """
    渲染科技感操盘记录大屏。
    """
    # 注入 CSS
    st.markdown(LIGHT_THEME_CSS, unsafe_allow_html=True)
    
    # 标题
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <div style="font-size: 1.8rem; font-weight: 600; color: #1a73e8;">
            操盘记录
        </div>
        <div style="color: #5f6368; font-size: 0.85rem; margin-top: 4px;">
            持仓监控与盈亏分析
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 获取数据
    positions = db_get_all_positions()
    watchlist = db_get_watchlist()
    all_symbols = set([p["symbol"] for p in positions] + watchlist)
    
    all_pnl_data = {}
    for symbol in all_symbols:
        pnl = db_compute_realized_pnl(symbol)
        if pnl["trade_count"] > 0:
            all_pnl_data[symbol] = pnl
    
    # 计算指标
    metrics, position_details = _calculate_portfolio_metrics(positions, all_pnl_data)
    
    # 状态指示器
    col_status, _ = st.columns([1, 3])
    with col_status:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
            <span class="status-dot online"></span>
            <span style="color: #137333; font-size: 0.85rem;">
                在线 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # 核心指标区域
    st.markdown("<div class='cyber-container'>", unsafe_allow_html=True)
    _render_cyber_metrics(metrics)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 使用 Tabs 组织内容
    tab1, tab2, tab3, tab4 = st.tabs(["持仓看板", "收益分析", "交易流水", "交易标绘"])
    
    with tab1:
        st.markdown("<div class='cyber-container' style='margin-top: 20px;'>", unsafe_allow_html=True)
        _render_position_cards(position_details)
        st.markdown("</div>", unsafe_allow_html=True)
        
        if all_pnl_data:
            st.markdown("<div style='margin-top: 30px;'>", unsafe_allow_html=True)
            _render_portfolio_stats(all_pnl_data, metrics)
            st.markdown("</div>", unsafe_allow_html=True)
    
    with tab2:
        st.markdown("<div class='cyber-container' style='margin-top: 20px;'>", unsafe_allow_html=True)
        _render_pnl_chart(all_pnl_data)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 盈亏分布图
        if all_pnl_data:
            st.markdown("<div style='margin-top: 30px;'>", unsafe_allow_html=True)
            st.markdown("<div class='cyber-title'>个股盈亏分布</div>", unsafe_allow_html=True)
            
            pnl_by_symbol = []
            for symbol, data in all_pnl_data.items():
                total = data.get('realized_pnl', 0)
                for pos in position_details:
                    if pos['symbol'] == symbol:
                        total += pos['floating_pnl']
                        break
                pnl_by_symbol.append({'symbol': symbol, 'pnl': total})
            
            pnl_df = pd.DataFrame(pnl_by_symbol).sort_values('pnl', ascending=True)
            
            fig = go.Figure(go.Bar(
                x=pnl_df['pnl'],
                y=pnl_df['symbol'],
                orientation='h',
                marker_color=['#137333' if x >= 0 else '#c5221f' for x in pnl_df['pnl']],
            ))
            
            fig.update_layout(
                template='plotly_white',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#202124'),
                xaxis=dict(title='盈亏', gridcolor='rgba(0,0,0,0.1)'),
                yaxis=dict(title='', gridcolor='rgba(0,0,0,0.1)'),
                height=max(300, len(pnl_df) * 35),
                margin=dict(l=80, r=40, t=40, b=40),
                showlegend=False,
            )
            
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
    
    with tab3:
        st.markdown("<div class='cyber-container' style='margin-top: 20px;'>", unsafe_allow_html=True)
        _render_trade_timeline(limit=50)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='cyber-container' style='margin-top: 20px;'>", unsafe_allow_html=True)
        _render_kline_with_trades()
        st.markdown("</div>", unsafe_allow_html=True)
