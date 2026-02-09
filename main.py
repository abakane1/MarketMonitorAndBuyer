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
    page_title="MarketMonitor v2.7.1",
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

# Initialize Database
from utils.database import init_db
init_db()

# --- Main App ---
st.title("📈 A股复盘与预判辅助系统 v2.7.1")

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
if app_mode == "策略实验室":
    from components.lab import render_strategy_lab
    render_strategy_lab()

elif app_mode == "提示词中心":
    st.header("🧠 智能体提示词中心 (Agent Prompt Center)")
    st.caption("管理各个智能体 (Agents) 的核心指令。基于通用架构，每个智能体均可自由组配任意大模型 (DeepSeek, Qwen 等) 进行驱动。")
    
    prompts = load_config().get("prompts", {})
    
    # Updated Tabs to reflect "Agents" concept
    tab1, tab2, tab3, tab4 = st.tabs(["Strategy Agent (策略智能体)", "Risk Agent (风控智能体)", "Tool Agent (工具/情报)", "Others (其他)"])
    
    # Define Descriptions & Titles (Role-Based Keys)
    p_map = {
        "proposer_system": "🧠 策略主帅系统设定 (Commander System)",
        "proposer_base": "🏗️ 策略基础模版 (Base Template)",
        "proposer_premarket_suffix": "📎 场景附录: 盘前规划 (Pre-market Suffix)",
        "proposer_intraday_suffix": "📎 场景附录: 盘中突发 (Intraday Suffix)",
        "proposer_noon_suffix": "📎 场景附录: 午间复盘 (Noon Suffix)",
        "proposer_simple_suffix": "📎 场景附录: 简易分析 (Simple Suffix)",
        "proposer_final_decision": "🏁 最终定稿指令 (Final Execution)",
        "refinement_instruction": "🔄 反思指令 (Refinement)",
        
        "blue_quant_sys": "🔢 数学官设定 (Quant Agent)",
        "blue_intel_sys": "🕵️ 情报官设定 (Intel Agent)",
        
        "reviewer_system": "🛡️ 风控官系统设定 (Reviewer System)",
        "reviewer_audit": "🛡️ 初审模版 (Audit Template)",
        "reviewer_final_audit": "⚖️ 终审模版 (Final Verdict)",
    }

    p_desc = {
        "proposer_base": "💡 说明: 定义了 LAG + GTO 的交易哲学和手牌（点位）描述逻辑。",
        "proposer_premarket_suffix": "💡 说明: 盘前规划专用。用于构建包含止损止盈的全天交易计划。",
        "proposer_intraday_suffix": "💡 说明: 盘中突发决策专用。侧重于实时盘口分析、极窄止损和即时行动建议。",
        "proposer_noon_suffix": "💡 说明: 午间复盘专用。包含上午收盘价与昨日收盘价对比，以及上午资金流向总结。",
        "proposer_simple_suffix": "💡 说明: 用于简单的资金流向和技术面分析总结。",
        "proposer_system": "💡 说明: 策略主帅系统设定。统筹量化与情报官的报告。",
        "proposer_final_decision": "💡 说明: 最终定稿指令 (Execution Order)。",
        "refinement_instruction": "💡 说明: 收到风控审查后的反思指令。核心强调独立自主 (Autonomy)。",
        
        "blue_quant_sys": "💡 说明: 数学官系统设定。专攻数字、资金流模型、盈亏比计算。",
        "blue_intel_sys": "💡 说明: 情报官系统设定。专攻新闻叙事、战绩回溯、预期差。",
        
        "reviewer_system": "💡 说明: 风控官角色设定，负责一致性审查。",
        "reviewer_audit": "💡 说明: (初审) 审核报告的生成模版。",
        "reviewer_final_audit": "💡 说明: (终审) 对优化后策略的最终裁决模版。",
        
        "metaso_query": "💡 说明: 指导 AI 将股票代码转化为有效的搜索 query 组合。",
        "metaso_parser": "💡 说明: 用于从杂乱的搜索结果中提取结构化的利好/利空情报。",
    }
    
    def render_prompts(prefix_list, exclude=None):
        count = 0
        target_keys = []
        for p in prefix_list:
            target_keys.extend([k for k in prompts.keys() if k.startswith(p)])
        
        # Add exact matches if any (like refinement_instruction)
        for p in prefix_list:
            if p in prompts and p not in target_keys:
                target_keys.append(p)
                
        sorted_keys = sorted(list(set(target_keys)))
        
        for k in sorted_keys:
            if k == "__NOTE__": continue
            if exclude and k in exclude: continue
            
            v = prompts[k]
            desc = p_desc.get(k, "")
            
            # Header Logic: Use Map if available, else auto-icon
            if k in p_map:
                header = p_map[k]
            else:
                header = k
                icon = "🗝️"
                if "base" in k: icon = "🏗️"
                elif "system" in k: icon = "🧠"
                elif "suffix" in k: icon = "📎"
                elif "refinement" in k: icon = "🔄"
                elif "quant" in k: icon = "🔢"
                elif "intel" in k: icon = "🕵️"
                elif "final" in k: icon = "🏁"
                header = f"{icon} {k}"
            
            with st.expander(header, expanded=False):
                st.text_area(f"Content ({k})", value=v, height=200, disabled=True)
                if desc: st.info(desc)
            count += 1
        return count

    with tab1:
        st.subheader("📝 Strategy Agent (策略智能体)")
        st.info("核心决策大脑。包含【主帅 Commander】、【数学官 Quant】、【情报官 Intel】。支持多模型挂载。")
        c = render_prompts(["proposer_", "refinement_instruction", "blue_"])
        if c == 0: st.info("暂无 Strategy Agent 提示词")

    with tab2:
        st.subheader("🛡️ Risk Agent (风控智能体)")
        st.info("独立风控审计系统。负责一致性审查 (Audit) 与 最终裁决 (Verdict)。")
        c = render_prompts(["reviewer_"])
        if c == 0: st.info("暂无 Risk Agent 提示词")

    with tab3:
        st.subheader("🔎 Tool Agent (工具/情报)")
        st.info("负责执行特定任务的工具型 Agent (如 Metaso 搜索解析)。")
        c = render_prompts(["metaso_"])
        if c == 0: st.info("暂无 Tool Agent 提示词")
        
    with tab4:
        st.subheader("其他 (Others)")
        # Render anything else
        all_prefixes = ("deepseek_", "metaso_", "qwen_", "refinement_instruction", "blue_")
        others = [k for k in prompts.keys() if not k.startswith(all_prefixes) and k != "refinement_instruction"]
        
        if others:
            for k in sorted(others):
                v = prompts[k]
                with st.expander(f"🔖 {k}", expanded=False):
                    st.code(v, language="text")
        else:
            st.caption("没有其他未分类的提示词。")

    # --- Optimization Section ---
    st.markdown("---")
    st.subheader("🚀 AI 智能优化")
    st.info("使用 DeepSeek R1 (Reasoner) 模型，基于 MECE 原则自动重构和优化所有提示词。")
    
    if "optimized_prompts" not in st.session_state:
        st.session_state.optimized_prompts = None
        st.session_state.optimization_reasoning = ""
        
    col_opt, col_clear = st.columns([1, 4])
    
    with col_opt:
        if st.button("开始全面优化", type="primary"):
            api_key = sidebar_data.get("deepseek_api_key")
            if not api_key:
                st.error("请先在侧边栏设置 DeepSeek API Key")
            else:
                with st.spinner("DeepSeek 正在深度思考中 (可能需要 30-60秒)..."):
                    from utils.prompt_optimizer import optimize_all_prompts
                    
                    current_prompts = load_config().get("prompts", {})
                    new_prompts, reasoning = optimize_all_prompts(api_key, current_prompts)
                    
                    if new_prompts:
                        st.session_state.optimized_prompts = new_prompts
                        st.session_state.optimization_reasoning = reasoning
                        st.success("优化完成！请在下方对比并确认。")
                    else:
                        st.error("优化失败，请查看日志或重试。")
                        if reasoning:
                            st.text_area("错误详情", reasoning)
                            
    with col_clear:
        if st.session_state.optimized_prompts and st.button("❌ 放弃/清空结果"):
            st.session_state.optimized_prompts = None
            st.session_state.optimization_reasoning = ""
            st.rerun()

    # --- Diff View & Confirmation ---
    if st.session_state.optimized_prompts:
        st.divider()
        st.subheader("🔍 优化对比 (Diff View)")
        
        # Reasoning
        if st.session_state.optimization_reasoning:
            with st.expander("🤔 查看 AI 思考过程 (Chain of Thought)", expanded=False):
                st.markdown(st.session_state.optimization_reasoning)
        
        new_prompts = st.session_state.optimized_prompts
        from utils.config import load_config
        old_prompts = load_config().get("prompts", {})
        
        # Iterating over keys to show diffs
        all_keys = set(old_prompts.keys()) | set(new_prompts.keys())
        
        # Sort keys to make diff view stable
        for key in sorted(all_keys):
            old_val = old_prompts.get(key, "(Missing)")
            new_val = new_prompts.get(key, "(Removed)")
            
            # Simple check for diff
            if old_val != new_val:
                with st.expander(f"📝 {key} (Has Changes)", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption("🔴 旧版本/Old")
                        st.code(old_val, language="text")
                    with c2:
                        st.caption("🟢 新版本/New")
                        st.code(new_val, language="text")
            else:
                with st.expander(f"✅ {key} (No Change)", expanded=False):
                     st.code(old_val, language="text")

        st.warning("⚠️ 确认保存将覆盖现有配置。")
        if st.button("✅ 确认保存并应用", type="primary"):
            from utils.config import save_config
            full_config = load_config()
            full_config["prompts"] = new_prompts
            save_config(full_config)
            
            st.session_state.optimized_prompts = None
            st.success("已保存全新优化后的提示词！")
            time.sleep(1)
            st.rerun()

elif app_mode == "复盘与预判":
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
                    
                    # Render Backtest Section (Removed: Moved to Strategy Lab)
                    # st.markdown("---")
                    # with st.expander("🛠️ 策略回测模拟 (Strategy Backtest)", expanded=False):
                    #    from utils.sim_ui import render_backtest_widget as render_backtest
                    #    render_backtest(code, current_holding_shares=get_position(code).get('shares', 0), current_holding_cost=get_position(code).get('cost', 0))
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
