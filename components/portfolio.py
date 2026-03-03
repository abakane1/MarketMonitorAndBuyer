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
# 科技感 CSS 样式
# =============================================================================
CYBERPUNK_CSS = """
<style>
/* 全局深色背景 */
[data-testid="stAppViewContainer"] {
    background: #0d1117;
}

/* 主容器 */
.cyber-container {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
}

/* 标题样式 */
.cyber-title {
    color: #58a6ff;
    font-size: 1.2rem;
    font-weight: 600;
    margin-bottom: 15px;
    padding-bottom: 8px;
    border-bottom: 1px solid #30363d;
}

/* 数据卡片 */
.metric-card {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
}

.metric-card:hover {
    border-color: #58a6ff;
}

.metric-value {
    font-size: 1.8rem;
    font-weight: 600;
    color: #f0f6fc;
}

.metric-value.positive {
    color: #3fb950;
}

.metric-value.negative {
    color: #f85149;
}

.metric-label {
    color: #8b949e;
    font-size: 0.85rem;
    margin-top: 8px;
}

/* 持仓卡片 */
.position-card {
    background: #21262d;
    border: 1px solid #30363d;
    border-left: 3px solid #58a6ff;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}

.position-card.etf {
    border-left-color: #a371f7;
}

.position-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.position-symbol {
    font-size: 1.1rem;
    font-weight: 600;
    color: #f0f6fc;
}

.position-name {
    color: #8b949e;
    font-size: 0.85rem;
}

.position-pnl {
    font-size: 1.1rem;
    font-weight: 600;
}

.position-pnl.positive {
    color: #3fb950;
}

.position-pnl.negative {
    color: #f85149;
}

/* 交易流水 */
.trade-item {
    background: #21262d;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 6px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-left: 3px solid transparent;
}

.trade-item.buy {
    border-left-color: #3fb950;
}

.trade-item.sell {
    border-left-color: #f85149;
}

.trade-time {
    color: #8b949e;
    font-size: 0.8rem;
}

.trade-symbol {
    color: #f0f6fc;
    font-weight: 500;
}

.trade-action {
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
}

.trade-action.buy {
    background: rgba(63, 185, 80, 0.15);
    color: #3fb950;
}

.trade-action.sell {
    background: rgba(248, 81, 73, 0.15);
    color: #f85149;
}

.trade-amount {
    color: #f0f6fc;
    font-weight: 500;
}

/* 标签 */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 500;
}

.badge-etf {
    background: rgba(163, 113, 247, 0.15);
    color: #a371f7;
}

.badge-stock {
    background: rgba(88, 166, 255, 0.15);
    color: #58a6ff;
}

/* 分割线 */
.cyber-divider {
    height: 1px;
    background: #30363d;
    margin: 20px 0;
}

/* 状态指示器 */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-dot.online {
    background: #3fb950;
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


def _calculate_portfolio_metrics(positions: list, all_pnl_data: dict):
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
    total_color = "#3fb950" if metrics['total_pnl'] >= 0 else "#f85149"
    st.markdown(f"""
    <div style="
        background: #161b22;
        border: 1px solid {total_color}50;
        border-radius: 10px;
        padding: 16px;
        margin: 16px 0;
        text-align: center;
    ">
        <div style="color: #8b949e; font-size: 0.85rem; margin-bottom: 6px;">总盈亏 (已实现 + 浮动)</div>
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
                            <div style="color: #8b949e; font-size: 0.75rem;">持仓 / 底仓</div>
                            <div style="color: #f0f6fc;">{pos['shares']} / {pos['base_shares']}</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">成本 → 现价</div>
                            <div style="color: #f0f6fc;">{pos['cost']:.3f} → {pos['price']:.3f}</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">市值</div>
                            <div style="color: #f0f6fc;">¥{pos['market_value']:,.0f}</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">浮动盈亏</div>
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
                            <div style="color: #8b949e; font-size: 0.75rem;">持仓</div>
                            <div style="color: #f0f6fc;">{pos['shares']} 股</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">成本 → 现价</div>
                            <div style="color: #f0f6fc;">{pos['cost']:.3f} → {pos['price']:.3f}</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">今日盈亏</div>
                            <div style="color: {'#3fb950' if pos['today_pnl'] >= 0 else '#f85149'};">{pos['today_pnl']:+,.0f}</div>
                        </div>
                        <div>
                            <div style="color: #8b949e; font-size: 0.75rem;">浮动盈亏</div>
                            <div class="position-pnl {pnl_class}">{pos['floating_pnl']:+,.0f}</div>
                        </div>
                    </div>
                    {f'<div style="margin-top: 8px; color: #d29922; font-size: 0.75rem;">底仓锁定: {pos["base_shares"]} 股</div>' if pos['base_shares'] > 0 else ''}
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
        line=dict(color='#58a6ff', width=2),
        fill='tozeroy',
        fillcolor='rgba(88, 166, 255, 0.1)',
    ))
    
    # 每日盈亏柱状图
    colors = ['#3fb950' if v >= 0 else '#f85149' for v in daily_values]
    fig.add_trace(go.Bar(
        x=sorted_dates,
        y=daily_values,
        name='每日盈亏',
        marker_color=colors,
        opacity=0.6,
        yaxis='y2'
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#c9d1d9'),
        title=dict(
            text='收益曲线',
            font=dict(size=16, color='#58a6ff'),
            x=0.5
        ),
        xaxis=dict(
            title='日期',
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
        ),
        yaxis=dict(
            title='累计盈亏',
            gridcolor='rgba(255,255,255,0.1)',
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
            font=dict(color='#8b949e')
        ),
        margin=dict(l=60, r=60, t=80, b=60),
        height=450,
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    
    st.plotly_chart(fig, use_container_width=True)


def _render_trade_timeline(limit: int = 30):
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
                <div style="color: #8b949e; font-size: 0.75rem;">{price:.3f} × {amount}</div>
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
        ("总交易次数", f"{total_trades} 笔", "#58a6ff"),
        ("累计买入", f"¥{total_buy:,.0f}", "#a371f7"),
        ("累计卖出", f"¥{total_sell:,.0f}", "#d29922"),
        ("持仓标的", f"{metrics['position_count']} 只", "#3fb950"),
    ]
    
    for col, (label, value, color) in zip(cols, stats):
        with col:
            st.markdown(f"""
            <div style="
                background: #21262d;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                border: 1px solid {color}30;
            ">
                <div style="color: {color}; font-size: 1.2rem; font-weight: 600;">{value}</div>
                <div style="color: #8b949e; font-size: 0.8rem; margin-top: 5px;">{label}</div>
            </div>
            """, unsafe_allow_html=True)


def render_portfolio_dashboard():
    """
    渲染科技感操盘记录大屏。
    """
    # 注入 CSS
    st.markdown(CYBERPUNK_CSS, unsafe_allow_html=True)
    
    # 标题
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <div style="font-size: 1.8rem; font-weight: 600; color: #58a6ff;">
            操盘记录
        </div>
        <div style="color: #8b949e; font-size: 0.85rem; margin-top: 4px;">
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
            <span style="color: #3fb950; font-size: 0.85rem;">
                在线 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # 核心指标区域
    st.markdown("<div class='cyber-container'>", unsafe_allow_html=True)
    _render_cyber_metrics(metrics)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 使用 Tabs 组织内容
    tab1, tab2, tab3 = st.tabs(["持仓看板", "收益分析", "交易流水"])
    
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
                marker_color=['#3fb950' if x >= 0 else '#f85149' for x in pnl_df['pnl']],
            ))
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#c9d1d9'),
                xaxis=dict(title='盈亏', gridcolor='rgba(255,255,255,0.1)'),
                yaxis=dict(title='', gridcolor='rgba(255,255,255,0.1)'),
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
