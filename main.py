import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.time_utils import is_trading_time
from utils.config import load_config, get_position
from components.sidebar import render_sidebar
from components.dashboard import render_stock_dashboard, render_strategy_section
# Note: render_stock_dashboard already handles strategy and intel hub rendering internally

# Page Configuration
st.set_page_config(
    page_title="MarketMonitor v1.3.1",
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
st.title("📈 A股智能盯盘与策略辅助系统 v1.3.1")

# Sidebar
sidebar_data = render_sidebar()
app_mode = sidebar_data["app_mode"]
selected_labels = sidebar_data["selected_labels"]
total_capital = sidebar_data["total_capital"]
risk_pct = sidebar_data["risk_pct"]
proximity_pct = sidebar_data["proximity_pct"]
auto_refresh = sidebar_data["auto_refresh"]
refresh_rate = sidebar_data["refresh_rate"]

# Main Area
if app_mode == "提示词中心":
    st.header("🧠 提示词模板中心")
    st.caption("查看并管理系统中使用的所有 AI 提示词模板。这些模板当前存储在 `user_config.json` 中。")
    
    prompts = load_config().get("prompts", {})
    
    tab1, tab2, tab3 = st.tabs(["DeepSeek (核心大脑)", "Metaso (秘塔搜索)", "Gemini (辅助研判)"])
    
    with tab1:
        st.subheader("DeepSeek 提示词")
        st.info("DeepSeek 负责核心的博弈逻辑分析和策略生成。")
        
        with st.expander("1️⃣ 基础博弈框架 (deepseek_base)", expanded=True):
            st.code(prompts.get("deepseek_base", ""), language="text")
            st.caption("💡 说明: 定义了 LAG + GTO 的交易哲学和手牌（点位）描述逻辑。")
        
        with st.expander("2️⃣ 策略验证后缀 (deepseek_research_suffix)", expanded=False):
            st.code(prompts.get("deepseek_research_suffix", ""), language="text")
            st.caption("💡 说明: 用于结合秘塔搜索的情报对算法信号进行“同意/驳回”验证。")
            
        with st.expander("3️⃣ 独立策略后缀 (deepseek_new_strategy_suffix)", expanded=False):
            st.code(prompts.get("deepseek_new_strategy_suffix", ""), language="text")
            st.caption("💡 说明: 用于跳过算法，完全独立构建包含止损止盈的交易计划。")

        with st.expander("4️⃣ 简单思考后缀 (deepseek_simple_suffix)", expanded=False):
            st.code(prompts.get("deepseek_simple_suffix", ""), language="text")
            st.caption("💡 说明: 用于简单的资金流向和技术面分析总结。")

    with tab2:
        st.subheader("Metaso 搜索提示词")
        st.info("Metaso 负责实时情报的检索和去伪存真。")
        
        with st.expander("1️⃣ 搜索关键词生成 (metaso_query)", expanded=True):
            st.code(prompts.get("metaso_query", ""), language="text")
            st.caption("💡 说明: 指导 AI 将股票代码转化为有效的搜索 query 组合。")
            
        with st.expander("2️⃣ 搜索备选方案 (metaso_query_fallback)", expanded=False):
            st.code(prompts.get("metaso_query_fallback", ""), language="text")
            
        with st.expander("3️⃣ 情报解析器 (metaso_parser)", expanded=False):
            st.code(prompts.get("metaso_parser", ""), language="text")
            st.caption("💡 说明: 用于从杂乱的搜索结果中提取结构化的利好/利空情报。")

    with tab3:
        st.subheader("Gemini 辅助提示词")
        
        with st.expander("1️⃣ 基础辅助 (gemini_base)", expanded=True):
            st.code(prompts.get("gemini_base", ""), language="text")

elif app_mode == "实时盯盘":
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
                    # Render Full Dashboard
                    render_stock_dashboard(code, name, total_capital, risk_pct, proximity_pct)
                    
                    # Render Backtest Section (Still separate to keep Dashboard clean or integrated? 
                    # Requirement said 'Strategy Backtest' is part of the view.
                    # Dashboard component does NOT include backtest widget.
                    # So we render it here.
                    
                    st.markdown("---")
                    with st.expander("🛠️ 策略回测模拟 (Strategy Backtest)", expanded=False):
                        from utils.sim_ui import render_backtest_widget as render_backtest
                        render_backtest(code, current_holding_shares=get_position(code).get('shares', 0), current_holding_cost=get_position(code).get('cost', 0))
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
