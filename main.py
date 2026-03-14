import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.time_utils import is_trading_time
from utils.config import load_config, get_position
from components.sidebar import render_sidebar
from components.dashboard import render_stock_dashboard, render_strategy_section

# Page Configuration
st.set_page_config(
    page_title="MarketMonitor v3.3.0",
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
    /* 移动端响应式优化 */
    @media (max-width: 768px) {
        /* 图表和卡片减小 padding */
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        /* 侧边栏按钮铺满 */
        .stButton button {
            width: 100%;
        }
        /* 避免表格字太大 */
        .dataframe {
            font-size: 0.75rem !important;
        }
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
st.title("📈 A股复盘与预判辅助系统 v3.3.0")

# Sidebar
sidebar_data = render_sidebar()
app_mode = sidebar_data["app_mode"]
selected_labels = sidebar_data["selected_labels"]
total_capital = sidebar_data["total_capital"]
risk_pct = sidebar_data["risk_pct"]
proximity_pct = sidebar_data["proximity_pct"]


# Main Area
if app_mode == "策略实验室":
    from components.lab import render_strategy_lab
    render_strategy_lab()

elif app_mode == "情报中心":
    from components.intel_timeline import render_intel_hub_page
    render_intel_hub_page()

elif app_mode == "操盘记录":
    from components.portfolio import render_portfolio_dashboard
    render_portfolio_dashboard()

elif app_mode == "交易日历":
    from components.calendar_view import render_calendar_view
    render_calendar_view()

elif app_mode == "提示词中心":
    st.header("🧠 智能体提示词中心 (Agent Prompt Center)")
    st.caption("管理各个智能体 (Agents) 的核心指令。基于通用架构，每个智能体均可自由组配任意大模型 (DeepSeek, Qwen 等) 进行驱动。")
    
    prompts = load_config().get("prompts", {})
    
    # ============================================================
    # 提示词分类定义 - 按照实际使用场景组织
    # ============================================================
    
    # 1. 策略生成 (Blue Team - 决策流程)
    STRATEGY_GENERATION = {
        "proposer_system": {
            "title": "🧠 策略主帅系统设定",
            "desc": "Blue Team Commander 的核心角色设定。定义 LAG + GTO 交易哲学、决策风格和输出格式要求。",
            "usage": "Used by: ai_advisor.py (DeepSeek), legion_advisor.py (Kimi Commander)",
            "category": "system"
        },
        "proposer_base": {
            "title": "🏗️ 策略基础模版", 
            "desc": "用户提示词的基础框架。包含持仓信息、价格数据、交易规则等变量占位符。",
            "usage": "Used by: ai_advisor.py::build_advisor_prompt()",
            "category": "template"
        },
        "proposer_premarket_suffix": {
            "title": "📋 场景附录: 盘前规划",
            "desc": "盘前规划场景专用。用于构建包含止损止盈的全天交易计划。",
            "usage": "Used by: Auto-Drive (盘前模式), Manual Analysis (盘前)",
            "category": "suffix"
        },
        "proposer_intraday_suffix": {
            "title": "📋 场景附录: 盘中突发",
            "desc": "盘中突发决策专用。侧重于实时盘口分析、极窄止损和即时行动建议。",
            "usage": "Used by: Manual Analysis (盘中模式)",
            "category": "suffix"
        },
        "proposer_noon_suffix": {
            "title": "📋 场景附录: 午间复盘",
            "desc": "午间复盘专用。包含上午收盘价与昨日收盘价对比，以及上午资金流向总结。",
            "usage": "Used by: Auto-Drive (午间模式), Manual Analysis (午间)",
            "category": "suffix"
        },
        "proposer_simple_suffix": {
            "title": "📋 场景附录: 简易分析",
            "desc": "用于简单的资金流向和技术面分析总结（'简洁'分析深度模式）。",
            "usage": "Used by: ai_advisor.py (analysis_depth='简洁')",
            "category": "suffix"
        },
        "proposer_extreme_scenarios": {
            "title": "⚠️ 极端场景应对手册",
            "desc": "定义极端市场情况（涨停、跌停、大幅跳空等）的处理策略。",
            "usage": "Used by: ai_advisor.py (通过 {load_principle} 注入)",
            "category": "principle"
        },
        "proposer_final_decision": {
            "title": "🏁 最终定稿指令",
            "desc": "第五步：终极决策。基于 Draft → Audit → Refine → Verdict 的全流程历史生成最终执行令。",
            "usage": "Used by: ai_advisor.py::build_final_decision_prompt()",
            "category": "template"
        },
        "refinement_instruction": {
            "title": "🔄 反思优化指令",
            "desc": "第三步：反思优化。收到红军审计报告后，蓝军如何进行策略修正的指令。强调独立自主 (Autonomy)。",
            "usage": "Used by: ai_advisor.py::build_refinement_prompt()",
            "category": "instruction"
        },
    }
    
    # 2. 风控审计 (Red Team - 审计流程)
    RISK_AUDIT = {
        "reviewer_system": {
            "title": "🛡️ 风控官系统设定",
            "desc": "Red Team 核心角色设定。定义一致性审查原则、LAG/GTO 体系评估标准。",
            "usage": "Used by: ai_advisor.py::build_red_team_prompt()",
            "category": "system"
        },
        "reviewer_audit": {
            "title": "📋 初审模版",
            "desc": "第二步：风险初审。红军对蓝军初始草案的第一次审计。",
            "usage": "Used by: ai_advisor.py::build_red_team_prompt(is_final_round=False)",
            "category": "template"
        },
        "reviewer_noon_audit": {
            "title": "📋 午间审计模版",
            "desc": "午间休息时的特殊审计模版，评估下午盘规划的风险。",
            "usage": "Used by: ai_advisor.py (market_status='CLOSED_NOON')",
            "category": "template"
        },
        "reviewer_final_audit": {
            "title": "⚖️ 终审模版",
            "desc": "第四步：终极裁决。红军对蓝军修正后策略的最终审计。",
            "usage": "Used by: ai_advisor.py::build_red_team_prompt(is_final_round=True)",
            "category": "template"
        },
    }
    
    # 3. 军团智能体 (MoE - 子Agent系统)
    LEGION_AGENTS = {
        "blue_quant_sys": {
            "title": "🔢 蓝军-数学官设定",
            "desc": "Blue Legion 子Agent。专攻数字、资金流模型、盈亏比计算。",
            "usage": "Used by: legion_advisor.py::run_blue_legion()",
            "category": "agent"
        },
        "blue_intel_sys": {
            "title": "🕵️ 蓝军-情报官设定", 
            "desc": "Blue Legion 子Agent。专攻新闻叙事、战绩回溯、预期差。",
            "usage": "Used by: legion_advisor.py::run_blue_legion()",
            "category": "agent"
        },
        "red_quant_auditor_system": {
            "title": "🔴 红军-数据审计官",
            "desc": "Red Legion 子Agent。专注于数据真实性、仓位风险和计算逻辑审计。",
            "usage": "Used by: legion_advisor.py::run_red_legion()",
            "category": "agent"
        },
        "red_intel_auditor_system": {
            "title": "🔴 红军-情报审计官",
            "desc": "Red Legion 子Agent。专注于新闻真实性、叙事偏见和盲点识别。",
            "usage": "Used by: legion_advisor.py::run_red_legion()",
            "category": "agent"
        },
        "red_commander_system": {
            "title": "🎯 红军最高指挥官",
            "desc": "Red Legion 总指挥。基于审计官报告对蓝军策略进行终极裁决。",
            "usage": "Used by: legion_advisor.py::run_red_legion()",
            "category": "agent"
        },
    }
    
    # 4. 交易原则 (双轨制 - ETF vs 股票)
    TRADING_PRINCIPLES = {
        "etf_position": {
            "title": "📊 ETF仓位管理原则",
            "desc": "ETF的仓位管理策略。越跌越买、网格交易、长期持有等原则。",
            "usage": "Used by: ai_advisor.py (ETF标的，注入到 {position_principle})",
            "category": "principle"
        },
        "etf_risk": {
            "title": "⚠️ ETF风险控制原则",
            "desc": "ETF的风险控制策略。钝化短线波动、底仓保护等。",
            "usage": "Used by: ai_advisor.py (ETF标的，注入到 {risk_principle})",
            "category": "principle"
        },
        "stock_position": {
            "title": "📈 股票仓位管理原则",
            "desc": "个股的仓位管理策略。动量突破、严格止损、高抛低吸等。",
            "usage": "Used by: ai_advisor.py (股票标的，注入到 {position_principle})",
            "category": "principle"
        },
        "stock_risk": {
            "title": "⚠️ 股票风险控制原则",
            "desc": "个股的风险控制策略。 tight stop、集中度管理等。",
            "usage": "Used by: ai_advisor.py (股票标的，注入到 {risk_principle})",
            "category": "principle"
        },
        "position_management": {
            "title": "📚 仓位管理通用原则",
            "desc": "通用的仓位管理原则，适用于所有标的类型。",
            "usage": "Used by: ai_advisor.py (通过 {load_principle} 注入)",
            "category": "principle"
        },
        "risk_management": {
            "title": "📚 风险管理通用原则",
            "desc": "通用的风险管理原则，适用于所有标的类型。",
            "usage": "Used by: ai_advisor.py (通过 {load_principle} 注入)",
            "category": "principle"
        },
        "market_microstructure": {
            "title": "🔬 市场微观结构",
            "desc": "A股市场微观结构分析，盘口语言、主力行为识别等。",
            "usage": "Used by: ai_advisor.py (通过 {load_principle} 注入)",
            "category": "principle"
        },
    }
    
    # 5. 工具与情报
    TOOLS_INTELLIGENCE = {
        "intelligence_processor_system": {
            "title": "🔍 金融情报分析师",
            "desc": "从杂乱的新闻流中提取核心市场信息，分类为利好/利空/中性。",
            "usage": "Used by: intelligence_processor.py::summarize_intelligence()",
            "category": "tool"
        },
        "qwen_agent_system": {
            "title": "🌐 金融情报搜集员",
            "desc": "利用Qwen的联网搜索能力，搜集并整理情报清单。",
            "usage": "Used by: qwen_agent.py::search_with_qwen()",
            "category": "tool"
        },
    }
    
    # 6. 默认Fallback（当主提示词缺失时使用）
    FALLBACK_DEFAULTS = {
        "fallback_quant_sys": {
            "title": "🔧 默认-量化分析引擎",
            "desc": "blue_quant_sys 缺失时的默认提示词。",
            "usage": "Fallback for: blue_quant_sys",
            "category": "fallback"
        },
        "fallback_intel_sys": {
            "title": "🔧 默认-市场情报分析师",
            "desc": "blue_intel_sys 缺失时的默认提示词。",
            "usage": "Fallback for: blue_intel_sys",
            "category": "fallback"
        },
        "fallback_red_quant_sys": {
            "title": "🔧 默认-风险审计官",
            "desc": "red_quant_auditor_system 缺失时的默认提示词。",
            "usage": "Fallback for: red_quant_auditor_system",
            "category": "fallback"
        },
        "fallback_red_intel_sys": {
            "title": "🔧 默认-合规审查官",
            "desc": "red_intel_auditor_system 缺失时的默认提示词。",
            "usage": "Fallback for: red_intel_auditor_system",
            "category": "fallback"
        },
    }
    
    # 7. 模型专属覆盖
    MODEL_OVERRIDES = {
        "deepseek_r1": {
            "title": "🤖 DeepSeek-R1 专属增强",
            "desc": "DeepSeek Reasoner 模型的专属系统提示词增强。",
            "usage": "Auto-appended to proposer_system when using DeepSeek-R1",
            "category": "override"
        },
        "kimi_k2_5": {
            "title": "🤖 Kimi-K2.5 专属增强",
            "desc": "月之暗面 Kimi-K2.5 模型的专属系统提示词增强。",
            "usage": "Auto-appended to proposer_system when using Kimi-K2.5",
            "category": "override"
        },
        "kimi_k2_5": {
            "title": "🤖 Kimi-K2.5 专属增强",
            "desc": "月之暗面 Kimi-K2.5 模型的专属系统提示词增强。",
            "usage": "Auto-appended to proposer_system when using Kimi-K2.5",
            "category": "override"
        },
    }
    
    # 合并所有定义
    ALL_PROMPT_DEFS = {}
    for d in [STRATEGY_GENERATION, RISK_AUDIT, LEGION_AGENTS, 
              TRADING_PRINCIPLES, TOOLS_INTELLIGENCE, FALLBACK_DEFAULTS, MODEL_OVERRIDES]:
        ALL_PROMPT_DEFS.update(d)
    
    # ============================================================
    # 渲染函数
    # ============================================================
    
    def render_prompt_section(prompt_defs: dict, section_title: str, section_icon: str):
        """渲染一个提示词分类区块"""
        st.subheader(f"{section_icon} {section_title}")
        
        count = 0
        for key, meta in prompt_defs.items():
            if key not in prompts:
                continue
                
            content = prompts[key]
            count += 1
            
            # 获取状态指示
            status_color = "🟢" if len(content) > 50 else "🟡"
            
            with st.expander(f"{status_color} {meta['title']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**📋 说明:** {meta['desc']}")
                    st.markdown(f"**🔧 用途:** `{meta['usage']}`")
                    st.markdown(f"**🏷️ 分类:** `{meta['category']}`")
                
                with col2:
                    # 字符数统计
                    st.metric("字符数", len(content))
                    st.caption(f"Key: `{key}`")
                
                st.markdown("---")
                
                # 编辑模式切换
                is_editing = st.checkbox("编辑当前提示词", key=f"edit_toggle_{key}")
                
                if is_editing:
                    new_content = st.text_area("提示词内容", value=content, height=350, key=f"ta_{key}", label_visibility="collapsed")
                    
                    if st.button("💾 保存修改", key=f"save_{key}", type="primary"):
                        if new_content != content:
                            import json
                            import os
                            config_path = "user_config.json"
                            
                            try:
                                # 完整读取现有配置
                                with open(config_path, "r", encoding="utf-8") as f:
                                    current_config = json.load(f)
                                
                                # 更新提示词
                                if "prompts" not in current_config:
                                    current_config["prompts"] = {}
                                current_config["prompts"][key] = new_content
                                
                                # 写回配置
                                with open(config_path, "w", encoding="utf-8") as f:
                                    json.dump(current_config, f, indent=4, ensure_ascii=False)
                                
                                st.success(f"提示词 `{key}` 已成功保存！")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"保存失败: {str(e)}")
                        else:
                            st.info("内容未改变，无需保存。")
                else:
                    st.text_area("提示词内容", value=content, height=250, disabled=True, 
                                key=f"ta_view_{key}", label_visibility="collapsed")
        
        if count == 0:
            st.info("该分类下暂无提示词配置")
        
        return count
    
    # ============================================================
    # 主界面 - Tab 布局
    # ============================================================
    
    tabs = st.tabs([
        "🎯 策略生成", 
        "🛡️ 风控审计", 
        "⚔️ 军团智能体",
        "📊 交易原则",
        "🔧 工具与情报",
        "🎛️ 模型配置"
    ])
    
    with tabs[0]:
        st.info("📝 **Blue Team 决策流程**: 策略生成是核心决策流程，包含盘前规划、盘中决策、午间复盘等多个场景。")
        render_prompt_section(STRATEGY_GENERATION, "策略生成提示词", "🎯")
    
    with tabs[1]:
        st.info("🛡️ **Red Team 审计流程**: 风控审计独立于策略生成，提供一致性审查和攻击性审计。")
        render_prompt_section(RISK_AUDIT, "风控审计提示词", "🛡️")
    
    with tabs[2]:
        st.info("⚔️ **Mixture of Experts (MoE)**: 军团智能体将复杂任务分解给专业子Agent处理。")
        render_prompt_section(LEGION_AGENTS, "军团智能体提示词", "⚔️")
    
    with tabs[3]:
        st.info("📊 **双轨交易原则**: ETF和股票采用不同的仓位管理和风险控制策略。")
        render_prompt_section(TRADING_PRINCIPLES, "交易原则提示词", "📊")
    
    with tabs[4]:
        st.info("🔧 **工具型Agent**: 执行特定任务的工具智能体，如情报搜集和分析。")
        c1 = render_prompt_section(TOOLS_INTELLIGENCE, "工具与情报提示词", "🔧")
        st.markdown("---")
        c2 = render_prompt_section(FALLBACK_DEFAULTS, "默认Fallback提示词", "🔧")
    
    with tabs[5]:
        st.info("🎛️ **模型专属配置**: 特定模型的系统提示词增强，会自动追加到基础系统提示词后。")
        render_prompt_section(MODEL_OVERRIDES, "模型专属覆盖", "🎛️")
    
    # ============================================================
    # 统计与概览
    # ============================================================
    
    st.markdown("---")
    st.subheader("📊 提示词统计概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_prompts = len([k for k in prompts.keys() if not k.startswith("__")])
    loaded_defs = sum(1 for k in ALL_PROMPT_DEFS.keys() if k in prompts)
    undefined_prompts = [k for k in prompts.keys() if k not in ALL_PROMPT_DEFS and not k.startswith("__")]
    
    with col1:
        st.metric("已加载提示词", total_prompts)
    with col2:
        st.metric("已分类提示词", loaded_defs)
    with col3:
        st.metric("未分类提示词", len(undefined_prompts))
    with col4:
        coverage = f"{loaded_defs/max(total_prompts,1)*100:.0f}%"
        st.metric("分类覆盖率", coverage)
    
    # 显示未分类提示词
    if undefined_prompts:
        with st.expander("🔍 未分类提示词 (需要整理)", expanded=False):
            for key in undefined_prompts:
                st.code(f"{key}: {len(prompts[key])} chars", language="text")
    
    # ============================================================
    # AI 智能优化
    # ============================================================
    
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
        # 获取当前选中的组合
        active_portfolio = sidebar_data.get("active_portfolio", "default")
        
        # Directly render the view
        def update_view(selected_labels, total_capital, risk_pct, proximity_pct, portfolio_id):
            # Removed main_container.container() to prevent layout bugs and performance issues
            st.caption(f"最后更新时间: {datetime.now().strftime('%H:%M:%S')}")
            
            # Switch to Tabs for Stocks
            tab_titles = ["📝 当日策略"] + [f"{label.split(' | ')[1]} ({label.split(' | ')[0]})" for label in selected_labels]
            stock_tabs = st.tabs(tab_titles)
            
            with stock_tabs[0]:
                from components.dashboard import render_daily_strategy_overview
                render_daily_strategy_overview(selected_labels)
            
            for idx, label in enumerate(selected_labels):
                code = label.split(" | ")[0]
                name = label.split(" | ")[1]
                
                with stock_tabs[idx + 1]:
                    # Render Full Dashboard with portfolio_id
                    render_stock_dashboard(code, name, total_capital, risk_pct, proximity_pct, portfolio_id)
                    
                    # Render Backtest Section (Removed: Moved to Strategy Lab)
                    # st.markdown("---")
                    # with st.expander("🛠️ 策略回测模拟 (Strategy Backtest)", expanded=False):
                    #    from utils.sim_ui import render_backtest_widget as render_backtest
                    #    render_backtest(code, current_holding_shares=get_position(code).get('shares', 0), current_holding_cost=get_position(code).get('cost', 0))
        # Initial Draw
        update_view(selected_labels, total_capital, risk_pct, proximity_pct, active_portfolio)
    
        # Loop for Auto Refresh
        st.caption("ℹ️ 点击左侧栏的【🔄 一键刷新实时数据】按钮以更新行情。")
    
    # Add Bottom Spacer to fix scrolling issue
    st.markdown('<div class="main-footer-spacer"></div>', unsafe_allow_html=True)
