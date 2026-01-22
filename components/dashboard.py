# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from utils.data_fetcher import get_stock_realtime_info, get_stock_minute_data, get_stock_fund_flow
from utils.storage import get_volume_profile
from utils.config import get_position, update_position, get_history, delete_transaction, get_allocation

from components.strategy_section import render_strategy_section
from components.intel_hub import render_intel_hub

def render_stock_dashboard(code: str, name: str, total_capital: float, risk_pct: float, proximity_pct: float):
    """
    渲染单个股票的完整仪表盘。
    """
    
    # 1. Fetch Real-time Info
    info = get_stock_realtime_info(code)
    if not info:
        st.error(f"无法获取 {name} 的数据")
        return
        
    price = info.get('price')
    
    # --- Position Management Section ---
    pos_data = get_position(code)
    shares_held = pos_data.get('shares', 0)
    avg_cost = pos_data.get('cost', 0.0)
    market_value = shares_held * price
    pnl = market_value - (shares_held * avg_cost)
    pnl_pct = (pnl / (shares_held * avg_cost)) * 100 if shares_held > 0 else 0.0
    
    with st.expander("💼 我的持仓 (Holdings)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前持有 (股)", shares_held)
        c2.metric("持仓成本", f"{avg_cost:.4f}")
        c3.metric("最新市值", round(market_value, 4))
        c4.metric("浮动盈亏", f"{pnl:.4f}", delta=f"{pnl_pct:.4f}%")
    
    with st.expander("📝 交易记账 (买入/卖出)", expanded=False):
        with st.form(key=f"trade_form_{code}"):
            col_t1, col_t2 = st.columns(2)
            trade_shares = col_t1.number_input("交易股数", min_value=100, step=100, key=f"s_{code}")
            trade_price = col_t2.number_input("交易价格", value=price, step=0.0001, format="%.4f", key=f"p_{code}")
            trade_action = st.radio("方向", ["买入", "卖出", "修正持仓(覆盖)"], horizontal=True, key=f"a_{code}")
            
            if st.form_submit_button("记录交易"):
                if trade_action == "买入":
                    update_position(code, trade_shares, trade_price, "buy")
                    st.success("买入记录已更新！")
                elif trade_action == "卖出":
                    update_position(code, trade_shares, trade_price, "sell")
                    st.success("卖出记录已更新！")
                else:
                    update_position(code, trade_shares, trade_price, "override")
                    st.success("持仓已强制修正！")
                time.sleep(1)
                st.rerun()
        
        st.markdown("---")
        st.caption("📜 交易记录 (History)")
        history = get_history(code)
        # Filter for transactions only
        tx_history = [h for h in history if h['type'] in ['buy', 'sell', 'override']]
        
        if tx_history:
            # Map types to Chinese
            type_map = {
                "buy": "买入",
                "sell": "卖出", 
                "override": "修正"
            }
            
            # Prepare Data for Table
            display_data = []
            # Note translation map
            note_map = {
                "Position Correction": "持仓修正",
                "Manual Buy": "手动买入",
                "Manual Sell": "手动卖出"
            }
            
            for entry in tx_history[::-1]:
                t_type = type_map.get(entry['type'], entry['type'])
                t_note = entry.get('note', '')
                t_note = note_map.get(t_note, t_note)
                
                display_data.append({
                    "选择": False,
                    "时间": entry['timestamp'],
                    "类型": t_type,
                    "价格": entry['price'],
                    "数量": int(entry['amount']),
                    "备注": t_note,
                    "raw_timestamp": entry['timestamp'] # Hidden key for deletion
                })
            
            df_display = pd.DataFrame(display_data)
            
            if not df_display.empty:
                # Show Data Editor
                edited_df = st.data_editor(
                    df_display,
                    column_config={
                        "选择": st.column_config.CheckboxColumn(
                            "选择",
                            help="勾选以删除",
                            default=False,
                            width="small"
                        ),
                        "时间": st.column_config.TextColumn("时间", width="medium"),
                        "类型": st.column_config.TextColumn("类型", width="small"),
                        "价格": st.column_config.NumberColumn("成交价", format="%.4f"),
                        "数量": st.column_config.NumberColumn("数量", format="%d"),
                        "备注": st.column_config.TextColumn("备注", width="large"),
                        "raw_timestamp": None # Hide this column
                    },
                    disabled=["时间", "类型", "价格", "数量", "备注"],
                    hide_index=True,
                    key=f"editor_{code}",
                    use_container_width=True
                )
                
                # Delete Button
                if st.button("🗑️ 删除选中记录", key=f"del_btn_{code}"):
                    to_delete = edited_df[edited_df["选择"] == True]
                    if not to_delete.empty:
                        deleted_count = 0
                        for _, row in to_delete.iterrows():
                            if delete_transaction(code, row['raw_timestamp']):
                                deleted_count += 1
                        
                        if deleted_count > 0:
                            st.success(f"已删除 {deleted_count} 条记录")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.warning("请先勾选要删除的记录")
            else:
                st.info("暂无交易记录")
        else:
            st.info("暂无交易记录")

    # --- Charts & Data Visualization ---
    
    # 1. Minute Data
    with st.expander("⏱️ 分时明细 (Minute Data)", expanded=False):
        hist_df = get_stock_minute_data(code)
        if not hist_df.empty:
            def get_direction(row):
                if row['收盘'] > row['开盘']: return "买盘"
                elif row['收盘'] < row['开盘']: return "卖盘"
                else: return "平盘"
            
            display_df = hist_df.copy()
            display_df['性质'] = display_df.apply(get_direction, axis=1)
            display_df = display_df[['时间', '收盘', '成交量', '性质']]
            display_df.columns = ['时间', '价格', '成交量', '性质']
            display_df = display_df.sort_values('时间', ascending=False)
            st.dataframe(display_df, width=1000, height=400, hide_index=True)
        else:
            st.warning("暂无实时数据")
            
    # 2. Volume Profile
    with st.expander("📊 筹码分布 (Volume Profile)", expanded=False):
        with st.expander("ℹ️ 什么是筹码分布？", expanded=False):
            st.markdown("""
            **筹码分布 (Volume by Price)**
            此图表统计了在统计区间内，每个价格价位上累计成交了多少股票。
            - **柱子高度**：代表该价格的成交量大小。
            - **作用**：成交量密集的区域（高柱子）往往构成**支撑位**或**阻力位**。
            """)
        
        vol_profile, meta = get_volume_profile(code)
        if not vol_profile.empty:
            start_str = str(meta.get('start_date'))
            end_str = str(meta.get('end_date'))
            st.caption(f"统计区间: {start_str} 至 {end_str}")
            
            fig_vol = go.Figure()
            fig_vol.add_trace(go.Bar(
                x=vol_profile['price_bin'],
                y=vol_profile['成交量'],
                name='成交量',
                marker_color='rgba(50, 100, 255, 0.6)'
            ))
            fig_vol.add_vline(x=price, line_dash="dash", line_color="red", annotation_text="当前价")
            fig_vol.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                yaxis_title="成交量",
                xaxis_title="价格",
                hovermode="x unified"
            )
            st.plotly_chart(fig_vol, use_container_width=True) # use_container_width=True in Streamlit params usually
        else:
            st.info("无本地历史数据。请点击侧边栏的“下载/更新历史数据”按钮。")
            
    # 3. Fund Flow
    with st.expander("💰 资金流向 (Fund Flow)", expanded=False):
        flow_data = get_stock_fund_flow(code)
        if flow_data and not flow_data.get("error"):
            f_col1, f_col2, f_col3 = st.columns(3)
            f_col1.metric("今日涨跌幅", flow_data.get('涨跌幅'))
            f_col2.metric("主力净流入 (净额)", flow_data.get('主力净流入'))
            f_col3.metric("主力净占比", flow_data.get('主力净占比'))
            st.divider()
            f_items = [
                {"项目": "超大单净流入", "数值": flow_data.get('超大单净流入')},
                {"项目": "大单净流入", "数值": flow_data.get('大单净流入')},
            ]
            st.table(f_items)
            st.caption("注：数据来自东方财富当日实时资金流向接口")
        elif flow_data and flow_data.get("error"):
             st.warning(f"无法获取资金流向数据: {flow_data.get('error')}")
        else:
             st.info("暂无资金流向数据")

    # Render Strategy + AI
    # Note: Strategy Section returns strategy result which Intel Hub might need (to show current signal)
    # So we capture it.
    strat_res = render_strategy_section(
        code, name, price, shares_held, avg_cost, total_capital, risk_pct, proximity_pct,
        pre_close=info.get('pre_close', 0.0)
    )
    
    # Render Intel Hub
    render_intel_hub(
        code, name, price, avg_cost, shares_held, strat_res, total_capital, get_allocation(code)
    )
