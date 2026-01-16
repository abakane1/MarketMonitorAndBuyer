import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from utils.data_fetcher import get_all_stocks_list, get_stock_realtime_info, get_stock_minute_data
from datetime import datetime
from utils.storage import save_minute_data, load_minute_data, get_volume_profile, has_minute_data
from utils.config import (
    load_selected_stocks, save_selected_stocks, 
    get_position, update_position,
    get_settings, save_settings,
    load_config, get_allocation, set_allocation, get_history
)
from utils.strategy import analyze_volume_profile_strategy
from utils.ai_advisor import ask_deepseek_advisor, ask_gemini_advisor
from utils.researcher import ask_metaso_research
from utils.indicators import calculate_indicators
from utils.time_utils import is_trading_time
from utils.intel_manager import get_claims, add_claims, update_claim_status, delete_claim, get_claims_for_prompt
from utils.ai_parser import parse_metaso_report

# Page Configuration
st.set_page_config(
    page_title="A股实时监控",
    layout="wide",
    page_icon="📈"
)

st.title("🇨🇳 A股实时监控系统")

# Sidebar: Controls
st.sidebar.header("设置")

# 1. Load Stock List (Cached)
with st.sidebar:
    # Silent load
    stock_df = get_all_stocks_list()
    
    if stock_df.empty:
        st.error("加载股票列表失败，请手动刷新。")
    else:
        stock_df['label'] = stock_df['代码'] + " | " + stock_df['名称']
    
    # 2. Load Saved Config
    saved_codes = load_selected_stocks()
    # Find matching labels for saved codes
    default_selections = []
    if not stock_df.empty:
        default_selections = stock_df[stock_df['代码'].isin(saved_codes)]['label'].tolist()
    
    # 3. Stock Selector with Limit Logic
    selected_labels = st.multiselect(
        "选择股票 (最多5只)",
        options=stock_df['label'] if not stock_df.empty else [],
        default=default_selections,
        max_selections=5,
        help="您最多只能选择5只股票进行监控。"
    )
    
    # Save selection on change
    current_codes = [label.split(" | ")[0] for label in selected_labels]
    if set(current_codes) != set(saved_codes):
        save_selected_stocks(current_codes)

    # 4. Settings Persistence (Capital & API Key)
    settings = get_settings()
    
    st.markdown("---")
    st.header("交易策略参数")
    
    # Capital
    default_capital = settings.get("total_capital", 100000.0)
    total_capital = st.number_input(
        "总资金 (元)", 
        min_value=10000.0, 
        value=float(default_capital), 
        step=10000.0,
        key="input_capital"
    )
    
    # Risk
    risk_pct = st.slider("单笔风险 (%)", 0.5, 5.0, 2.0) / 100.0
    
    # API Key
    st.markdown("---")
    st.header("AI 专家设置")
    
    # Ensure session state is initialized from settings if not already set
    if "input_apikey" not in st.session_state:
        st.session_state.input_apikey = settings.get("deepseek_api_key", "")
    if "input_gemini" not in st.session_state:
        st.session_state.input_gemini = settings.get("gemini_api_key", "")

    # DeepSeek
    deepseek_api_key = st.text_input(
        "DeepSeek API Key", 
        type="password", 
        help="支持 DeepSeek Reasoner (R1) 模型",
        key="input_apikey"
    )

    # Gemini
    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="Google Gemini API Key",
        key="input_gemini"
    )

    # Metasota (Research)
    st.markdown("---")
    st.header("Metaso 秘塔搜索")
    
    if "input_metaso_key" not in st.session_state:
        st.session_state.input_metaso_key = settings.get("metaso_api_key", "")
    
    metaso_api_key = st.text_input(
        "Metaso API Key",
        type="password",
        help="用于深度研报分析",
        key="input_metaso_key"
    )
    
    # Advanced Config for Metaso (Base URL)
    with st.expander("高级设置 (Endpoint)", expanded=False):
         if "input_metaso_url" not in st.session_state:
             st.session_state.input_metaso_url = settings.get("metaso_base_url", "https://metaso.cn/api/v1")
             
         metaso_base_url = st.text_input(
             "API Base URL",
             value=st.session_state.input_metaso_url,
             help="默认: https://metaso.cn/api/v1",
             key="input_metaso_url"
         )
    
    # Save Settings if Changed
    new_settings = {
        "total_capital": total_capital,
        "deepseek_api_key": deepseek_api_key,
        "gemini_api_key": gemini_api_key,
        "metaso_api_key": metaso_api_key,
        "metaso_base_url": metaso_base_url
    }
    
    # Check if changed
    if (new_settings["total_capital"] != default_capital or 
        new_settings["deepseek_api_key"] != settings.get("deepseek_api_key", "") or
        new_settings["gemini_api_key"] != settings.get("gemini_api_key", "") or
        new_settings["metaso_api_key"] != settings.get("metaso_api_key", "") or
        new_settings["metaso_base_url"] != settings.get("metaso_base_url", "")):
        save_settings(new_settings)

    # Refresh Settings
    auto_refresh = st.checkbox("自动刷新", value=False)
    refresh_rate = st.slider("刷新间隔 (秒)", 5, 60, 10)
    
    st.markdown("---")
    st.header("数据管理")
    
    # Data controls
    col_update, col_sync = st.sidebar.columns(2)
    if col_update.button("🔄 更新股票列表"):
        with st.spinner("Updating Stock List..."):
            get_all_stocks_list(force_update=True)
            st.success("Stock list updated!")
            time.sleep(1)
            st.rerun()
        progress_bar.empty()

# Main Area
if not selected_labels:
    st.info("请在左侧侧边栏选择股票开始监控。")
else:
    # Container for the grid
    main_container = st.empty()
    
    def update_view():
        with main_container.container():
            st.caption(f"最后更新时间: {datetime.now().strftime('%H:%M:%S')}")
            
            # Switch to Tabs for Stocks
            stock_names = [label.split(" | ")[1] for label in selected_labels]
            stock_tabs = st.tabs(stock_names)
            
            for idx, label in enumerate(selected_labels):
                code = label.split(" | ")[0]
                name = label.split(" | ")[1]
                
                with stock_tabs[idx]:
                    # 1. Fetch Real-time Info
                    info = get_stock_realtime_info(code)
                    if not info:
                        st.error(f"无法获取 {name} 的数据")
                        continue
                        
                    price = info.get('price')
                    
                    # --- Position Management Section ---
                    pos_data = get_position(code)
                    shares_held = pos_data.get('shares', 0)
                    avg_cost = pos_data.get('cost', 0.0)
                    market_value = shares_held * price
                    pnl = market_value - (shares_held * avg_cost)
                    pnl_pct = (pnl / (shares_held * avg_cost)) * 100 if shares_held > 0 else 0.0
                    
                    st.subheader("我的持仓")
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
                    
                    st.divider()

                    # --- Strategy Section ---
                    
                    # 1. Capital Allocation UI
                    current_alloc = get_allocation(code)
                    eff_capital = total_capital # Default
                    
                    with st.expander("⚙️ 资金配置 (Capital Allocation)", expanded=False):
                        new_alloc = st.number_input(
                            f"本股资金限额 (0表示使用总资金)",
                            value=float(current_alloc),
                            min_value=0.0,
                            step=10000.0,
                            format="%.0f",
                            key=f"alloc_{code}",
                            help="限制该股票的最大持仓市值。策略将利用此数值计算建议仓位。"
                        )
                        if st.button("保存限额", key=f"save_{code}"):
                            set_allocation(code, new_alloc)
                            st.success(f"已保存! 本股资金限额: {new_alloc}")
                            time.sleep(0.5)
                            st.rerun()
                            
                    if new_alloc > 0:
                        eff_capital = new_alloc

                    # Calculate Strategy
                    vol_profile_for_strat, _ = get_volume_profile(code)
                    strat_res = analyze_volume_profile_strategy(price, vol_profile_for_strat, eff_capital, risk_pct, current_shares=shares_held)
                    
                    with st.expander("🤖 交易策略分析 (筹码支撑/阻力)", expanded=True):
                        s_col1, s_col2, s_col3 = st.columns(3)
                        
                        signal = strat_res.get('signal')
                        color = "grey"
                        if signal == "买入": color = "green"
                        if signal == "卖出": color = "red"
                        
                        s_col1.markdown(f"**信号**: :{color}[{signal}]")
                        s_col2.metric("建议仓位 (股)", strat_res.get('quantity', 0))
                        
                        # Dynamic Label: Stop Loss vs Profit Guard
                        sl_val = strat_res.get('stop_loss', 0)
                        sl_label = "止损参考"
                        if shares_held > 0 and sl_val > avg_cost:
                            sl_label = "止盈/保护 (Profit Guard)"
                            
                        s_col3.metric(sl_label, sl_val)
                        
                        st.info(f"💡 **决策依据**: {strat_res.get('reason')}")
                        st.caption(f"关键点位 - 支撑: {strat_res.get('support')} | 阻力: {strat_res.get('resistance')}")
                        
                        # Metasota Research + DeepSeek Analysis
                        st.markdown("---")
                        
                        # Market Status & refresh logic
                        is_closed = not is_trading_time()
                        has_local_data = len(get_claims(code)) > 0
                        
                        force_refresh = False
                        if is_closed and has_local_data:
                            force_refresh = st.checkbox("🔄 强制刷新情报 (Force Refresh)", value=False, help="当前为闭盘时间且本地已有数据，默认优先使用本地数据。勾选此项将强制重新联网检索。")
                        
                        if st.button("🔍 秘塔 x DeepSeek 联合深度研判", key=f"ask_metaso_{code}", use_container_width=True):
                            # Move prompts loading here to ensure scope safety
                            prompts = load_config().get("prompts", {})
                            if not metaso_api_key or not deepseek_api_key:
                                st.warning("请在侧边栏设置 Metaso API Key 和 DeepSeek API Key")
                            else:
                                research_report = ""
                                user_feedback_msg = ""
                                
                                # Logic: Determines whether to fetch or use local
                                should_fetch = True
                                if is_closed and has_local_data and not force_refresh:
                                    should_fetch = False
                                    user_feedback_msg = "✅ 休市期间，已为您自动加载【本地存量情报】进行研判 (无需重复消耗流量)。"
                                
                                if should_fetch:
                                    # 1. Metaso Fetch
                                    with st.spinner(f"🔍 步骤1: 秘塔正在全网检索 {name} 的最新研报与新闻 (约20秒)..."):
                                        context = {
                                            "code": code,
                                            "name": name,
                                            "price": price,
                                            "cost": avg_cost, 
                                            "support": strat_res.get('support'), 
                                            "resistance": strat_res.get('resistance'),
                                            "signal": signal,
                                            "reason": strat_res.get('reason'),
                                            "quantity": strat_res.get('quantity'),
                                            "target_position": strat_res.get('target_position', 0),
                                            "stop_loss": strat_res.get('stop_loss')
                                        }
                                        # Use configured base URL
                                        metaso_base = load_config().get("settings", {}).get("metaso_base_url", "https://metaso.cn/api/v1")
                                        
                                        # Get query template
                                        metaso_tpl = prompts.get("metaso_query", "")
                                        
                                        # Inject Existing Claims Context? 
                                        # Actually, if we fetch new, we want the AI to see old specific items to avoid dupes?
                                        # Yes, passing intelligent context.
                                        existing_lines = get_claims_for_prompt(code)
                                        if existing_lines and "{existing_claims}" not in metaso_tpl:
                                             metaso_tpl += f"\n\n(Known Facts to Ignore/Verify):\n{existing_lines}"
                                        
                                        research_report = ask_metaso_research(
                                            metaso_api_key, 
                                            metaso_base, 
                                            context, 
                                            query_template=metaso_tpl
                                        )
                                        
                                        with st.expander(f"📄 秘塔搜索原始情报", expanded=False):
                                            st.markdown(research_report)
    
                                        # --- Intelligence Processing Start ---
                                        # Get existing
                                        existing = get_claims(code)
                                        
                                        # Parse and Compare
                                        parse_res = parse_metaso_report(deepseek_api_key, research_report, existing)
                                        
                                        new_claims = parse_res.get("new_claims", [])
                                        contradictions = parse_res.get("contradictions", [])
                                        
                                        # Auto-save valid new claims (User can delete later)
                                        if new_claims:
                                            add_claims(code, new_claims)
                                            st.success(f"📚 已自动收录 {len(new_claims)} 条新情报到数据库")
                                            
                                        if contradictions:
                                            st.error(f"⚠️ 发现 {len(contradictions)} 条潜在矛盾信息！")
                                            for c in contradictions:
                                                st.warning(f"**旧情报**: {c.get('old_content')}\n\n**新情报**: {c.get('new_content')}\n\n**DeepSeek裁判**: {c.get('judgement')}")
                                        # --- Intelligence Processing End ---
                                        
                                else:
                                    # Use Local Data
                                    st.info(user_feedback_msg)
                                    # Construct a report from local claims
                                    local_claims = get_claims(code)
                                    research_report = "【本地情报汇总 (Market Closed)】\n"
                                    for c in local_claims:
                                        research_report += f"- [{c['timestamp']}] {c['content']}\n"
                                    
                                    with st.expander(f"📄 本地情报详情", expanded=False):
                                        st.text(research_report)

                                # 2. DeepSeek Analysis
                                with st.spinner(f"🧠 步骤2: DeepSeek 正在结合情报与技术指标进行综合研判..."):
                                    # Calculate Indicators
                                    minute_df = load_minute_data(code)
                                    tech_indicators = calculate_indicators(minute_df)
                                    
                                    # Add Daily Stats (OHLCV)
                                    # info is available from loop scope
                                    daily_stats_str = (
                                        f"Open:{info.get('open', 'N/A')} "
                                        f"High:{info.get('high', 'N/A')} "
                                        f"Low:{info.get('low', 'N/A')} "
                                        f"Vol:{info.get('volume', 'N/A')} "
                                        f"Amt:{info.get('amount', 'N/A')}"
                                    )
                                    tech_indicators["daily_stats"] = daily_stats_str
                                    
                                    # Show Indicators to user
                                    if tech_indicators:
                                        with st.expander("📊 关键技术指标 (RSI/MACD/KDJ)", expanded=False):
                                            st.json(tech_indicators)
                                            
                                    advice, reasoning, used_prompt = ask_deepseek_advisor(
                                        deepseek_api_key, 
                                        context, 
                                        research_context=research_report,
                                        technical_indicators=tech_indicators,
                                        prompt_templates=prompts
                                    )
                                    
                                    with st.expander("🕵️ 查看发送给AI的完整提示词 (Prompt)", expanded=False):
                                        st.text(used_prompt)
                                    
                                    st.markdown("### 🏆 联合研判结论")
                                    if reasoning:
                                        with st.expander("💭 DeepSeek 思考过程", expanded=True):
                                            st.markdown(f"```text\n{reasoning}\n```")
                                    st.success(advice)
                        
                        # Intelligence Center UI
                        st.markdown("---")
                        with st.expander("🗃️ 股票情报数据库 (Intelligence Hub)", expanded=False):
                            current_claims = get_claims(code)
                            if not current_claims:
                                st.info("暂无收录的情报。请点击上方【联合研判】进行抓取。")
                            else:
                                for idx, item in enumerate(current_claims):
                                    col_c1, col_c2, col_c3 = st.columns([0.7, 0.15, 0.15])
                                    with col_c1:
                                        # Color code status
                                        status_map = {
                                            "verified": "🟢",
                                            "disputed": "🟠",
                                            "false_info": "❌"
                                        }
                                        status_icon = status_map.get(item['status'], "⚪")
                                        
                                        # Strikethrough if false
                                        content_display = item['content']
                                        if item['status'] == 'false_info':
                                            content_display = f"~~{content_display}~~ (用户人工证伪)"
                                            
                                        st.markdown(f"**{status_icon} [{item['timestamp']}]** {content_display}")
                                        if item.get('note'):
                                            st.caption(f"备注: {item['note']}")
                                    
                                    with col_c2:
                                        if item['status'] != 'false_info':
                                            if st.button("标记为假", key=f"fake_{item['id']}"):
                                                update_claim_status(code, item['id'], "false_info")
                                                st.rerun()
                                    with col_c3:
                                        if st.button("删除/无关", key=f"del_{item['id']}"):
                                            delete_claim(code, item['id'])
                                            st.rerun()
                                    st.divider()

                        # --- Transaction History Log ---
                        st.markdown("---")
                        with st.expander("📜 操作日志 (History)", expanded=False):
                            history = get_history(code)
                            if history:
                                # Reverse to show newest first
                                df_hist = pd.DataFrame(history[::-1])
                                # Rename columns for better display
                                df_hist = df_hist.rename(columns={
                                    "timestamp": "时间", 
                                    "type": "类型", 
                                    "price": "价格/数值", 
                                    "amount": "数量/额度", 
                                    "note": "备注"
                                })
                                st.dataframe(df_hist, use_container_width=True)
                            else:
                                st.info("暂无操作记录")

                    st.divider()

                    # 2. Sub-Tabs for Details
                    sub_tab1, sub_tab2 = st.tabs(["分时明细", "筹码分布"])
                    
                    with sub_tab1:
                        # Fetch Live Minute Data
                        hist_df = get_stock_minute_data(code)
                        if not hist_df.empty:
                            # Logic: Close > Open => Buy (买盤), Close < Open => Sell (卖盤), else Flat (平盘)
                            def get_direction(row):
                                if row['收盘'] > row['开盘']:
                                    return "买盘"
                                elif row['收盘'] < row['开盘']:
                                    return "卖盘"
                                else:
                                    return "平盘"
                            
                            display_df = hist_df.copy()
                            display_df['性质'] = display_df.apply(get_direction, axis=1)
                            
                            # Select cols
                            display_df = display_df[['时间', '收盘', '成交量', '性质']]
                            display_df.columns = ['时间', '价格', '成交量', '性质']
                            
                            # Sort by time desc
                            display_df = display_df.sort_values('时间', ascending=False)
                            
                            st.dataframe(display_df, width=1000, height=400, hide_index=True)
                        else:
                            st.warning("暂无实时数据")
                            
                    with sub_tab2:
                        # Explanation
                        with st.expander("ℹ️ 什么是筹码分布？", expanded=False):
                            st.markdown("""
                            **筹码分布 (Volume by Price)**
                            
                            此图表统计了在统计区间内，每个价格价位上累计成交了多少股票。
                            - **柱子高度**：代表该价格的成交量大小。
                            - **作用**：成交量密集的区域（高柱子）通常代表着大量的换手，往往构成该股票的**支撑位**（价格跌到此容易反弹）或**阻力位**（价格涨到此容易回调）。
                            """)
                        
                        # Fetch Local Volume Profile
                        # Updated to unpack tuple
                        vol_profile, meta = get_volume_profile(code)
                        
                        if not vol_profile.empty:
                            # Show Time Range
                            start_str = str(meta.get('start_date'))
                            end_str = str(meta.get('end_date'))
                            st.caption(f"统计区间: {start_str} 至 {end_str}")
                            
                            # Vertical Bar Chart (Price on X, Volume on Y)
                            fig_vol = go.Figure()
                            fig_vol.add_trace(go.Bar(
                                x=vol_profile['price_bin'], # Price on X
                                y=vol_profile['成交量'],       # Volume on Y
                                name='成交量',
                                marker_color='rgba(50, 100, 255, 0.6)'
                            ))
                            # Add current price line (Vertical line on X axis)
                            fig_vol.add_vline(x=price, line_dash="dash", line_color="red", annotation_text="当前价")
                            
                            fig_vol.update_layout(
                                margin=dict(l=0, r=0, t=10, b=0),
                                height=300,
                                yaxis_title="成交量",
                                xaxis_title="价格",
                                hovermode="x unified"
                            )
                            st.plotly_chart(fig_vol, use_container_width=True)
                        else:
                            st.info("无本地历史数据。请点击侧边栏的“下载/更新历史数据”按钮。")

    # Initial Draw
    update_view()

    # Loop for Auto Refresh
    if auto_refresh:
        # Check Trading Hours
        if is_trading_time():
            time.sleep(refresh_rate)
            st.rerun()
        else:
            st.caption("😴 当前非交易时间，自动刷新已暂停。")
