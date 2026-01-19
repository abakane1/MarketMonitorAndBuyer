import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from utils.data_fetcher import get_all_stocks_list, get_stock_realtime_info, get_stock_minute_data, get_stock_fund_flow, get_stock_fund_flow_history
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
from utils.researcher import ask_metaso_research, ask_metaso_research_loop
from utils.indicators import calculate_indicators
from utils.time_utils import is_trading_time
from utils.intel_manager import get_claims, add_claims, update_claim_status, delete_claim, get_claims_for_prompt
from utils.ai_parser import parse_metaso_report, extract_bracket_content

# Page Configuration
st.set_page_config(
    page_title="MarketMonitor v1.2.1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom Styles ---
st.markdown("""
<style>
    /* 缩小情报数据库中的按钮尺寸 */
    .stButton button {
        padding: 0.2rem 0.5rem;
        font-size: 0.8rem;
        height: auto;
        min-height: 0;
    }
    /* 压缩分割线间距 */
    hr {
        margin: 0.5rem 0px !important;
    }
    /* 紧凑列表项样式 */
    .claim-item {
        padding: 5px 0;
        border-bottom: 1px solid #f0f2f6;
    }
    /* 修复底部滚动留白 */
    .main-footer-spacer {
        height: 100px;
    }
</style>
""", unsafe_allow_html=True)

# --- Session Init ---
if 'selected_code' not in st.session_state:
    st.session_state.selected_code = None

# --- Main App ---
st.title("📈 A股智能盯盘与策略辅助系统 v1.2.1")

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
    risk_pct = st.slider(
        "单笔风险 (%)", 
        0.5, 
        5.0, 
        2.0,
        help="决定每次交易的最大亏损额。例如: 总资金10万, 设置2%, 则单笔交易止损金额控制在2000元以内。"
    ) / 100.0
    st.caption("ℹ️ 风控: 单笔亏损不超过总资金的 X%。自动计算仓位大小。")
    
    # Strategy Sensitivity
    default_prox = settings.get("proximity_threshold", 0.012) * 100 # Default 1.2%
    proximity_pct_input = st.slider(
        "策略敏感度/接近阈值 (%)", 
        0.5, 
        5.0, 
        float(default_prox), 
        0.1,
        help="判定价格是否'到达'关键点位的距离。数值越大，信号越容易触发（更激进）；数值越小，要求点位越精准（更保守）。"
    )
    st.caption(f"ℹ️ 灵敏度: 价格在 支撑/阻力位 ±{proximity_pct_input:.1f}% 范围内视为有效。")
    proximity_pct = proximity_pct_input / 100.0
    
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
        "metaso_base_url": metaso_base_url,
        "proximity_threshold": proximity_pct
    }
    
    # Check if changed
    if (new_settings["total_capital"] != default_capital or 
        new_settings["deepseek_api_key"] != settings.get("deepseek_api_key", "") or
        new_settings["gemini_api_key"] != settings.get("gemini_api_key", "") or
        new_settings["metaso_api_key"] != settings.get("metaso_api_key", "") or
        new_settings["metaso_base_url"] != settings.get("metaso_base_url", "") or
        abs(new_settings["proximity_threshold"] - settings.get("proximity_threshold", 0.012)) > 0.0001):
        save_settings(new_settings)

    # Refresh Settings
    auto_refresh = st.checkbox("自动刷新", value=False)
    refresh_rate = st.slider("刷新间隔 (秒)", 5, 60, 10)
    
    st.markdown("---")
    st.header("数据管理")
    
    # Data controls
    col_update, col_sync = st.sidebar.columns(2)
    col_u = col_update.button("🔄 更新股票列表")
    if col_u:
        with st.spinner("Updating Stock List..."):
            get_all_stocks_list(force_update=True)
            st.success("Stock list updated!")
            time.sleep(1)
            st.rerun()

    if col_sync.button("📉 下载/更新历史数据"):
        if not selected_labels:
            st.warning("请先选择股票")
        else:
            with st.spinner("Downloading historical data..."):
                for label in selected_labels:
                    code_to_sync = label.split(" | ")[0]
                    save_minute_data(code_to_sync)
                    # 强制更新资金流向数据
                    get_stock_fund_flow_history(code_to_sync, force_update=True)
                st.success(f"已更新 {len(selected_labels)} 只股票的历史数据！")
                time.sleep(1)
                st.rerun()

# Main Area
if not selected_labels:
    st.info("请在左侧侧边栏选择股票开始监控。")
else:
    # Directly render the view
    def update_view():
        # Removed main_container.container() to prevent layout bugs and performance issues
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
                        # Reverse to show newest first
                        df_hist = pd.DataFrame(tx_history[::-1])
                        
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
                                width="stretch" # Fix width issue
                            )
                            
                            # Delete Button
                            if st.button("🗑️ 删除选中记录", key=f"del_btn_{code}"):
                                to_delete = edited_df[edited_df["选择"] == True]
                                if not to_delete.empty:
                                    from utils.config import delete_transaction
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
                vol_profile_for_strat, vol_meta = get_volume_profile(code)
                strat_res = analyze_volume_profile_strategy(
                    price, 
                    vol_profile_for_strat, 
                    eff_capital, 
                    risk_pct, 
                    current_shares=shares_held,
                    proximity_threshold=proximity_pct
                )
                
                # --- Algorithm Section (Simplified) ---
                with st.expander("⚙️ 算法建议 (Algorithm)", expanded=False):
                    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
                    
                    signal = strat_res.get('signal')
                    color = "grey"
                    if signal == "买入": color = "green"
                    if signal == "卖出": color = "red"
                    
                    s_col1.markdown(f"**建议方向**: :{color}[{signal}]")
                    s_col2.metric("建议股数", strat_res.get('quantity', 0))
                    
                    sl_val = strat_res.get('stop_loss', 0)
                    sl_label = "止损参考"
                    if shares_held > 0 and sl_val > avg_cost: sl_label = "利润保护"
                    s_col3.metric(sl_label, sl_val)
                    
                    tp_val = strat_res.get('take_profit', 'N/A')
                    s_col4.metric("止盈参考", tp_val)
                    
                    st.caption(f"💡 逻辑依据: {strat_res.get('reason')}")
                    st.caption(f"📊 支撑: {strat_res.get('support')} | 阻力: {strat_res.get('resistance')}")

                # --- AI Section (Elevated) ---
                with st.expander("🧠 AI 深度研判 (AI Analysis)", expanded=False):
                    # Check for AI Strategy
                    from utils.storage import get_latest_strategy_log
                    ai_strat_log = get_latest_strategy_log(code)
                    
                    if ai_strat_log:
                        content = ai_strat_log['result']
                        reasoning = ai_strat_log.get('reasoning', '')
                        ts = ai_strat_log['timestamp'][5:16]
                        st.caption(f"📅 最后生成: {ts}")
                        
                        # --- Simple Parser (Reuse original logic) ---
                        import re
                        ai_signal = "N/A"
                        pos_txt = "N/A"
                        stop_loss_txt = "N/A"
                        entry_txt = "N/A"
                        take_profit_txt = "N/A"

                        block_match = re.search(r"【决策摘要】(.*)", content, re.DOTALL)
                        if block_match:
                            block_content = block_match.group(1)
                            s_match = re.search(r"方向:\s*(\[)?(.*?)(])?\n", block_content)
                            if not s_match: s_match = re.search(r"方向:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                            if s_match: ai_signal = s_match.group(2).replace("[","").replace("]","").strip()
                            
                            e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?\n", block_content)
                            if not e_match: e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                            if e_match: entry_txt = e_match.group(2).replace("[","").replace("]","").strip()
                                
                            p_match = re.search(r"(?:建议|目标)?(?:股数|仓位):\s*(\[)?(.*?)(])?(?:\n|$)", block_content)
                            if p_match: pos_txt = p_match.group(2).replace("[","").replace("]","").strip()
                                
                            sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                            if not sl_match: sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                            if sl_match: stop_loss_txt = sl_match.group(3).replace("[","").replace("]","").strip()
                                
                            tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                            if not tp_match: tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                            if tp_match: take_profit_txt = tp_match.group(4).replace("[","").replace("]","").strip()

                        else:
                            signal_match = re.search(r"【(买入|卖出|做空|观望|持有)】", content)
                            ai_signal = signal_match.group(1) if signal_match else "N/A"
                            lines = content.split('\n')
                            for line in lines:
                                if "止损" in line: stop_loss_txt = line.split(":")[-1].strip().replace("元","")[:10]
                                if "止盈" in line or "目标" in line: take_profit_txt = line.split(":")[-1].strip().replace("元","")[:10]
                                if "股数" in line or "仓位" in line: pos_txt = line.split(":")[-1].strip()[:10]
                        
                        if "N/A" in ai_signal and "观望" in content: ai_signal = "观望"
                        
                        ai_col1, ai_col2, ai_col3, ai_col4, ai_col5 = st.columns(5)
                        s_color = "grey"
                        if ai_signal in ["买入", "做多"]: s_color = "green"
                        if ai_signal in ["卖出", "做空"]: s_color = "red"
                        pos_val, pos_note = extract_bracket_content(pos_txt if pos_txt != "N/A" else "--")
                        sl_val, sl_note = extract_bracket_content(stop_loss_txt if stop_loss_txt != "N/A" else "--")
                        tp_val, tp_note = extract_bracket_content(take_profit_txt if take_profit_txt != "N/A" else "--")
                        entry_val, entry_note = extract_bracket_content(entry_txt if entry_txt != "N/A" else "--")

                        ai_col1.markdown(f"**AI建议**: :{s_color}[{ai_signal}]")
                        
                        ai_col2.metric("建议价格", entry_val)
                        if entry_note: ai_col2.caption(f"({entry_note})")
                        
                        ai_col3.metric("建议股数", pos_val)
                        if pos_note: ai_col3.caption(f"({pos_note})")
                        
                        ai_col4.metric("止损参考", sl_val)
                        if sl_note: ai_col4.caption(f"({sl_note})")
                        
                        ai_col5.metric("止盈参考", tp_val)
                        if tp_note: ai_col5.caption(f"({tp_note})")
                        
                        with st.expander("📄 查看完整策略报告", expanded=False):
                            st.markdown(content)
                            if reasoning:
                                st.divider()
                                st.caption("AI 思考过程 (Chain of Thought)")
                                st.text(reasoning)

                    else:
                        st.info("👋 暂无 AI 独立策略记录。")

                    st.markdown("---")
                    # Control Buttons
                    col_btn1, col_btn2 = st.columns(2)
                    start_verify = False
                    start_new = False
                    with col_btn1:
                         if st.button("⚖️ 验证当前策略 (Validate)", key=f"btn_val_{code}", use_container_width=True):
                             start_verify = True
                    with col_btn2:
                         if st.button("💡 生成新策略 (New Strategy)", key=f"btn_new_{code}", use_container_width=True):
                             start_new = True
                             
                    if start_verify or start_new:
                         target_suffix_key = "deepseek_research_suffix"
                         if start_new: target_suffix_key = "deepseek_new_strategy_suffix"
                         prompts = load_config().get("prompts", {})
                         if not deepseek_api_key:
                             st.warning("请在侧边栏设置 DeepSeek API Key")
                         else:
                             with st.spinner(f"🧠 DeepSeek 研判中..."):
                                 from utils.intel_manager import get_claims_for_prompt
                                 context = {
                                     "code": code, "name": name, "price": price, "cost": avg_cost, 
                                     "current_shares": shares_held, "support": strat_res.get('support'), 
                                     "resistance": strat_res.get('resistance'), "signal": signal,
                                     "reason": strat_res.get('reason'), "quantity": strat_res.get('quantity'),
                                     "target_position": strat_res.get('target_position', 0),
                                     "stop_loss": strat_res.get('stop_loss'), "capital_allocation": current_alloc,
                                     "total_capital": total_capital, "known_info": get_claims_for_prompt(code)
                                 }
                                 from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision
                                 minute_df = load_minute_data(code)
                                 tech_indicators = calculate_indicators(minute_df)
                                 tech_indicators["daily_stats"] = aggregate_minute_to_daily(minute_df, precision=get_price_precision(code))
                                 
                                 full_intel_context = get_claims_for_prompt(code)
                                 advice, reasoning, used_prompt = ask_deepseek_advisor(
                                     deepseek_api_key, context, research_context=full_intel_context, 
                                     technical_indicators=tech_indicators, fund_flow_data=get_stock_fund_flow(code),
                                     fund_flow_history=get_stock_fund_flow_history(code), prompt_templates=prompts,
                                     suffix_key=target_suffix_key
                                 )
                                 from utils.storage import save_research_log
                                 save_research_log(code, used_prompt, advice, reasoning)
                                 st.success("研判完成！已自动更新。")
                                 time.sleep(0.5)
                                 st.rerun()

                    # --- Nested History (Inside AI Analysis) ---
                    st.markdown("---")
                    with st.expander("📜 历史研报记录 (Research History)", expanded=False):
                        from utils.storage import load_research_log, delete_research_log
                        logs = load_research_log(code)
                        if not logs:
                            st.info("暂无历史记录")
                        else:
                            log_options = {}
                            for log in logs[::-1]:
                                ts = log.get('timestamp', 'N/A')
                                res_snippet = log.get('result', '')[:30].replace('\n', ' ') + "..."
                                label = f"{ts} | {res_snippet}"
                                log_options[label] = log
                            selected_label = st.selectbox("选择历史记录", options=list(log_options.keys()), key=f"hist_sel_{code}")
                            if selected_label:
                                selected_log = log_options[selected_label]
                                s_ts = selected_log.get('timestamp', 'N/A')
                                st.markdown(f"#### 🗓️ {s_ts}")
                                st.write(selected_log.get('result', ''))
                                if selected_log.get('reasoning'):
                                    with st.expander("💭 思考过程", expanded=False):
                                        st.markdown(f"```text\n{selected_log['reasoning']}\n```")
                                
                                # --- Added: Show Prompt ---
                                if selected_log.get('prompt'):
                                    with st.expander("📝 DeepSeek 提示词", expanded=False):
                                        st.markdown(f"```text\n{selected_log['prompt']}\n```")
                                if st.button("🗑️ 删除此记录", key=f"del_rsch_{code}_{s_ts}"):
                                    if delete_research_log(code, s_ts):
                                        st.success("已删除")
                                        time.sleep(0.5)
                                        st.rerun()

                
                # Intelligence Center UI
                with st.expander("🗃️ 股票情报数据库 (Intelligence Hub)", expanded=False):
                    # --- Top Action Buttons ---
                    col_top1, col_top2 = st.columns([0.5, 0.5])
                    
                    # 1. Metaso Search Button
                    if col_top1.button("🔍 秘塔深度搜索", key=f"btn_metaso_{code}", use_container_width=True):
                        if not metaso_api_key or not deepseek_api_key:
                            st.warning("请在侧边栏设置 Metaso API Key 和 DeepSeek API Key")
                        else:
                            with st.spinner(f"🔍 秘塔正在检索 {name} 的最新情报..."):
                                from utils.researcher import parse_metaso_report
                                from utils.intel_manager import add_claims
                                prompts = load_config().get("prompts", {})
                                context = {
                                    "code": code, "name": name, "price": price, "cost": avg_cost, 
                                    "current_shares": shares_held, "support": strat_res.get('support'), 
                                    "resistance": strat_res.get('resistance'), "signal": signal,
                                    "reason": strat_res.get('reason'), "capital_allocation": current_alloc,
                                    "total_capital": total_capital
                                }
                                metaso_base = load_config().get("settings", {}).get("metaso_base_url", "https://metaso.cn/api/v1")
                                research_report = ask_metaso_research_loop(
                                    metaso_api_key, metaso_base, deepseek_api_key, context, 
                                    base_query_template=prompts.get("metaso_query", ""),
                                    existing_claims=get_claims(code),
                                    metaso_parser_template=prompts.get("metaso_parser", "")
                                )
                                parse_res = parse_metaso_report(deepseek_api_key, research_report, get_claims(code), prompt_template=prompts.get("metaso_parser", ""))
                                if parse_res.get("new_claims"): 
                                    add_claims(code, parse_res["new_claims"])
                                    st.success(f"成功收集到 {len(parse_res['new_claims'])} 条新情报！")
                                else:
                                    st.info("未发现显著的新增情报。")
                                time.sleep(1)
                                st.rerun()

                    # 2. Dedupe Button
                    if f"dedupe_results_{code}" not in st.session_state:
                        st.session_state[f"dedupe_results_{code}"] = None
                    
                    current_claims = get_claims(code)
                    if col_top2.button("🧹 扫描重复并清理", key=f"btn_dedupe_{code}", use_container_width=True):
                        if not current_claims:
                            st.info("暂无情报可供清理")
                        else:
                            from utils.ai_parser import find_duplicate_candidates
                            with st.spinner("正在对比语义分析重复项 (DeepSeek)..."):
                                ds_key = st.session_state.get("input_apikey", "")
                                if not ds_key:
                                    st.error("请先设置 DeepSeek API Key")
                                else:
                                    dupe_groups = find_duplicate_candidates(ds_key, current_claims)
                                    if not dupe_groups:
                                        st.success("未发现重复情报！")
                                        st.session_state[f"dedupe_results_{code}"] = None
                                    else:
                                        st.session_state[f"dedupe_results_{code}"] = dupe_groups
                                        st.rerun()

                    # --- Dedupe Review Interface (Top) ---
                    dupe_groups = st.session_state.get(f"dedupe_results_{code}")
                    if dupe_groups:
                        st.warning(f"⚠️ 发现 {len(dupe_groups)} 组重复情报，请确认合并操作：")
                        for g_idx, group in enumerate(dupe_groups):
                            with st.container(border=True):
                                st.caption(f"重复组 #{g_idx+1} (原因: {group['reason']})")
                                items = group['items']
                                rec_id = group.get('recommended_keep')
                                cols = st.columns(len(items))
                                for i, item_obj in enumerate(items):
                                    is_rec = (item_obj['id'] == rec_id)
                                    with cols[i]:
                                        box_color = "green" if is_rec else "grey"
                                        st.markdown(f":{box_color}[**ID: {item_obj['id']}**]")
                                        if is_rec: st.caption("✨ 建议保留")
                                        st.text_area("内容", item_obj['content'], height=250, disabled=True, key=f"txt_{item_obj['id']}")
                                        if st.button(f"✅ 保留此条 (合并)", key=f"keep_{item_obj['id']}"):
                                            others = [x['id'] for x in items if x['id'] != item_obj['id']]
                                            for oid in others: delete_claim(code, oid)
                                            st.toast(f"✅ 已合并，保留了 ID: {item_obj['id']}")
                                            current_groups = st.session_state.get(f"dedupe_results_{code}", [])
                                            if g_idx < len(current_groups):
                                                current_groups.pop(g_idx)
                                                st.session_state[f"dedupe_results_{code}"] = current_groups
                                            time.sleep(1)
                                            st.rerun()
                                if st.button(f"忽略此组", key=f"ignore_{g_idx}_{code}"):
                                    group_ids = [str(x['id']) for x in items]
                                    from utils.intel_manager import mark_claims_distinct
                                    mark_claims_distinct(code, group_ids)
                                    current_groups = st.session_state.get(f"dedupe_results_{code}", [])
                                    if g_idx < len(current_groups):
                                        current_groups.pop(g_idx)
                                        st.session_state[f"dedupe_results_{code}"] = current_groups
                                    st.rerun()
                    
                    st.markdown("---")
                    current_claims = get_claims(code)
                    if not current_claims:
                        st.info("暂无收回的情报。请点击上方按钮进行抓取。")
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
                                    
                                st.markdown(f"**{status_icon} [识别日期: {item['timestamp']}]** {content_display}")
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
                            # 移除 st.divider() 减少间距
                            
                            # 移除下方原本的去重清理逻辑及 UI
                                        





                # 2. Detailed Data Sections (Style Unified)
                with st.expander("⏱️ 分时明细 (Minute Data)", expanded=False):
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
                        
                with st.expander("📊 筹码分布 (Volume Profile)", expanded=False):
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
                        st.plotly_chart(fig_vol, width="stretch")
                    else:
                        st.info("无本地历史数据。请点击侧边栏的“下载/更新历史数据”按钮。")
                        
                with st.expander("💰 资金流向 (Fund Flow)", expanded=False):
                    # Fetch Cached Fund Flow
                    flow_data = get_stock_fund_flow(code)
                    if flow_data and not flow_data.get("error"):
                        # Transform single dict to clear UI components
                        
                        # 1. Headline Metrics
                        f_col1, f_col2, f_col3 = st.columns(3)
                        f_col1.metric("今日涨跌幅", flow_data.get('涨跌幅'))
                        f_col2.metric("主力净流入 (净额)", flow_data.get('主力净流入'))
                        f_col3.metric("主力净占比", flow_data.get('主力净占比'))
                        
                        st.divider()
                        
                        # 2. Detailed Table
                        f_items = [
                            {"项目": "超大单净流入", "数值": flow_data.get('超大单净流入')},
                            {"项目": "大单净流入", "数值": flow_data.get('大单净流入')},
                            # Note: data_fetcher currently exposes only these. 
                            # We can display the raw dict as a nice table too.
                        ]
                        st.table(f_items)
                        
                        st.caption("注：数据来自东方财富当日实时资金流向接口")
                    elif flow_data and flow_data.get("error"):
                         st.warning(f"无法获取资金流向数据: {flow_data.get('error')}")
                    else:
                         st.info("暂无资金流向数据")

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
    
    # Add Bottom Spacer to fix scrolling issue
    st.markdown('<div class="main-footer-spacer"></div>', unsafe_allow_html=True)
