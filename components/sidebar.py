# -*- coding: utf-8 -*-
"""
侧边栏组件模块
包含股票关注列表管理、交易参数配置、API Key 设置等功能
"""
import streamlit as st
import time

from utils.data_fetcher import get_stock_fund_flow_history, validate_stock_code
from utils.storage import save_minute_data
from utils.config import get_settings, save_settings
from utils.database import (
    db_get_watchlist_with_names,
    db_add_watchlist_with_name,
    db_remove_watchlist,
    db_get_all_portfolios,
    db_add_portfolio,
    db_delete_portfolio
)


def render_sidebar() -> dict:
    """
    渲染侧边栏并返回用户配置
    
    Returns:
        dict: 包含用户选择的股票和配置参数
    """
    # 导航
    st.sidebar.title("🎮 功能导航")
    app_mode = st.sidebar.radio("选择页面", ["复盘与预判", "操盘记录", "提示词中心", "策略实验室", "交易日历"], index=0)
    
    st.sidebar.markdown("---")
    
    # [NEW] Quick Trade (NLP Enhanced)
    with st.sidebar.expander("⚡️ 智能交易 (NLP Trade)", expanded=True):
        st.caption("💡 支持自然语言，例如：\"买1000股588200\"、\"清仓600076\"")
        
        trade_cmd = st.text_input(
            "交易指令", 
            placeholder="例如: 帮我买1000股588200 @2.435",
            key="quick_trade_input"
        )
        
        # 显示常用示例
        with st.expander("📖 查看示例指令", expanded=False):
            st.markdown("""
            **买入示例：**
            - `帮我买1000股588200`
            - `588200买入1000股，价格2.435`
            - `加仓588200 5000股`
            - `市价买入600076 1000股`
            
            **卖出示例：**
            - `卖出300股600076，价格4.5`
            - `清仓588200`
            - `减仓600076一半`
            - `帮我卖掉588200全部持仓`
            
            **说明：**
            - 支持"股"或"手"（1手=100股）
            - 不填价格则使用实时市价
            - 支持"市价"、"现价"等关键词
            """)
        
        col_parse, col_exec = st.columns([1, 2])
        
        # 解析状态存储
        parse_key = "parsed_trade_result"
        if parse_key not in st.session_state:
            st.session_state[parse_key] = None
        
        with col_parse:
            if st.button("🔍 解析", key="btn_parse_trade"):
                if not trade_cmd.strip():
                    st.error("请输入交易指令")
                else:
                    from utils.nlp_trade_parser import parse_natural_language_trade, format_trade_summary
                    
                    with st.spinner("正在解析..."):
                        parsed = parse_natural_language_trade(trade_cmd)
                        st.session_state[parse_key] = parsed
                        
                    if parsed["valid"]:
                        st.success("✓ 解析成功")
                    else:
                        st.error(f"✗ {parsed['error']}")
        
        # 显示解析结果
        if st.session_state[parse_key]:
            parsed = st.session_state[parse_key]
            if parsed["valid"]:
                from utils.nlp_trade_parser import format_trade_summary
                st.markdown(format_trade_summary(parsed))
                
                # 执行按钮
                with col_exec:
                    if st.button("✅ 确认执行", type="primary", key="btn_exec_trade"):
                        from utils.trade_manager import execute_trade
                        from utils.database import db_get_position
                        
                        code = parsed["symbol"]
                        action = parsed["action"]
                        price = parsed["price"]
                        qty = parsed["quantity"]
                        current_portfolio = st.session_state.get("active_portfolio", "default")
                        
                        # 处理特殊数量标记
                        if qty == -1:  # 半仓
                            pos = db_get_position(code)
                            if pos and pos["shares"] > 0:
                                qty = pos["shares"] // 2
                                qty = (qty // 100) * 100  # 取整到100的倍数
                                if qty < 100:
                                    st.error(f"持仓{pos['shares']}股，不足以卖出半仓（至少100股）")
                                    st.stop()
                            else:
                                st.error(f"未持有{code}，无法执行半仓操作")
                                st.stop()
                        elif qty == -2:  # 全部清仓
                            pos = db_get_position(code)
                            if pos and pos["shares"] > 0:
                                qty = pos["shares"]
                            else:
                                st.error(f"未持有{code}，无法清仓")
                                st.stop()
                        
                        # 显示确认信息
                        st.info(f"执行: {action.upper()} {code} {qty}股 @ {price}")
                        
                        with st.spinner(f"正在执行交易..."):
                            res = execute_trade(
                                code, action, price, qty, 
                                note="NLP智能交易", 
                                portfolio_id=current_portfolio
                            )
                        
                        if res["success"]:
                            st.success(res["message"])
                            st.session_state[parse_key] = None  # 清空解析结果
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(res["message"])

    # [NEW] 投资组合管理 (Multi-Portfolio)
    st.sidebar.markdown("---")
    st.sidebar.header("💼 投资组合选择")
    
    portfolios = db_get_all_portfolios()
    # Handle edge case where DB might not be initialized properly
    if not portfolios:
        portfolios = [{"id": "default", "name": "主组合"}]
        
    portfolio_options = {p["id"]: f"{p['name']} ({p['id']})" for p in portfolios}
    
    # Initialize session state for portfolio
    if "active_portfolio" not in st.session_state:
        st.session_state.active_portfolio = "default"
        
    # Selector
    selected_portfolio_id = st.sidebar.selectbox(
        "当前激活的组合",
        options=list(portfolio_options.keys()),
        format_func=lambda x: portfolio_options[x],
        index=list(portfolio_options.keys()).index(st.session_state.active_portfolio) if st.session_state.active_portfolio in portfolio_options else 0,
        key="portfolio_selector"
    )
    
    # Update Session State
    if selected_portfolio_id != st.session_state.active_portfolio:
        st.session_state.active_portfolio = selected_portfolio_id
        st.rerun()
        
    with st.sidebar.expander("管理投资组合 / 新建组合", expanded=False):
        new_pf_id = st.text_input("组合ID (限英文字母/数字)", key="new_pf_id")
        new_pf_name = st.text_input("组合名称", key="new_pf_name")
        if st.button("创建新组合"):
            if new_pf_id and new_pf_name:
                import re
                if not re.match(r'^[a-zA-Z0-9_]+$', new_pf_id):
                    st.error("组合ID只能包含字母、数字和下划线")
                elif new_pf_id in portfolio_options:
                    st.error("该组合ID已存在")
                else:
                    db_add_portfolio(new_pf_id, new_pf_name)
                    st.success(f"已创建组合: {new_pf_name}")
                    st.session_state.active_portfolio = new_pf_id
                    time.sleep(0.5)
                    st.rerun()
            else:
                st.warning("ID 和 名称 不能为空")
                
        st.markdown("---")
        if selected_portfolio_id != "default":
            if st.button("🗑️ 删除当前组合", type="primary"):
                if db_delete_portfolio(selected_portfolio_id):
                    st.success("组合已删除")
                    st.session_state.active_portfolio = "default"
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("删除失败")

    st.sidebar.header("📌 关注列表管理")
    
    with st.sidebar:
        # --- 添加股票区域 ---
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            new_code = st.text_input(
                "输入股票代码",
                placeholder="例: 600076",
                label_visibility="collapsed",
                key="input_new_stock_code"
            )
        with col_btn:
            add_clicked = st.button("添加", type="primary", key="btn_add_stock")
        
        if add_clicked and new_code:
            new_code = new_code.strip()
            if not new_code:
                st.warning("请输入股票代码")
            else:
                with st.spinner(f"正在验证 {new_code}..."):
                    result = validate_stock_code(new_code)
                    if result['valid']:
                        # 检查是否已在关注列表中
                        existing = [s for s, _ in db_get_watchlist_with_names()]
                        if new_code in existing:
                            st.warning(f"⚠️ {new_code} 已在关注列表中")
                        else:
                            db_add_watchlist_with_name(result['code'], result['name'])
                            st.success(f"✅ 已添加: {result['code']} {result['name']}")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.error(f"❌ 无效代码: {new_code}（需要6位数字）")
        
        # --- 当前关注列表 ---
        watchlist = db_get_watchlist_with_names()
        
        # [NEW] Sort by Holding Value (shares * current_price)
        # 1. Get all positions
        from utils.database import db_get_all_positions
        all_positions = db_get_all_positions()
        pos_map = {p['symbol']: p['shares'] for p in all_positions}
        
        # 2. Get current prices for valuation (optional, but better sort)
        # For simplicity and speed, we might just sort by shares count if price is not readily available in sidebar
        # taking 'shares' as proxy for 'size' as requested ("持股的大小")
        # If we really want market value, we need real-time price, which might be slow.
        # Let's sort by shares first (descending).
        
        # Sort logic: Primary = Shares (Desc), Secondary = Added Time (Implicit/Original Order)
        # watchlist is list of (symbol, name)
        watchlist.sort(key=lambda x: pos_map.get(x[0], 0), reverse=True)
        
        if watchlist:
            st.caption(f"当前关注 ({len(watchlist)} 只)")
            for symbol, name in watchlist:
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    display_name = name if name != symbol else symbol
                    st.markdown(f"**{symbol}** {display_name}")
                with col_del:
                    if st.button("❌", key=f"remove_{symbol}", help=f"移除 {symbol}"):
                        db_remove_watchlist(symbol)
                        st.rerun()
        else:
            st.info("关注列表为空，请添加股票代码开始监控。")
        
        # 构建 selected_labels（向后兼容 main.py 的消费格式）
        selected_labels = [f"{symbol} | {name}" for symbol, name in watchlist]
        
        # --- 设置参数 ---
        settings = get_settings()
        
        st.markdown("---")
        st.header("AI 分析深度")
        analysis_depth = st.select_slider(
            "选择分析深度",
            options=["简洁", "标准", "深度"],
            value=settings.get("analysis_depth", "标准"),
            help="简洁：极速决策及结论；标准：完整场景推演；深度：包含多时间框架与反事实思考。"
        )

        st.markdown("---")
        st.header("交易策略参数")
        
        # 总资金
        default_capital = settings.get("total_capital", 100000.0)
        total_capital = st.number_input(
            "总资金 (元)",
            min_value=10000.0,
            value=float(default_capital),
            step=10000.0,
            key="input_capital"
        )
        
        # 风险比例
        risk_pct = st.slider(
            "单笔风险 (%)",
            0.5,
            5.0,
            2.0,
            help="决定每次交易的最大亏损额。例如: 总资金10万, 设置2%, 则单笔交易止损金额控制在2000元以内。"
        ) / 100.0
        st.caption("ℹ️ 风控: 单笔亏损不超过总资金的 X%。自动计算仓位大小。")
        
        # 策略敏感度
        default_prox = settings.get("proximity_threshold", 0.012) * 100
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
        
        # API Key 设置
        st.markdown("---")
        st.header("AI 专家设置")
        
        # 初始化 session state
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
        
        # Qwen (Tongyi Qianwen) - Now only for web search
        if "input_qwen" not in st.session_state:
            st.session_state.input_qwen = settings.get("qwen_api_key", "")
            
        qwen_api_key = st.text_input(
            "Qwen API Key (DashScope) - 仅用于搜索",
            type="password",
            help="阿里云 DashScope API Key，仅用于情报搜索（不再用于策略生成或审计）",
            key="input_qwen"
        )
        
        # Metaso 设置
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

        # Kimi (Moonshot)
        if "input_kimi" not in st.session_state:
            st.session_state.input_kimi = settings.get("kimi_api_key", "")
            
        kimi_api_key = st.text_input(
            "Kimi API Key (Kimi 2.5 / Code API)",
            type="password",
            help="Moonshot AI API Key，用于红队审查",
            key="input_kimi"
        )
        
        if "input_kimi_url" not in st.session_state:
            st.session_state.input_kimi_url = settings.get("kimi_base_url", "https://api.moonshot.cn/v1")
        
        # 高级设置
        with st.expander("高级设置 (Endpoint)", expanded=False):
            if "input_metaso_url" not in st.session_state:
                st.session_state.input_metaso_url = settings.get("metaso_base_url", "https://metaso.cn/api/v1")
            
            metaso_base_url = st.text_input(
                "Metaso API Base URL",
                value=st.session_state.input_metaso_url,
                help="默认: https://metaso.cn/api/v1",
                key="input_metaso_url"
            )
            
            kimi_base_url = st.text_input(
                "Kimi API Base URL",
                value=st.session_state.input_kimi_url,
                help="默认: https://api.moonshot.cn/v1",
                key="input_kimi_url"
            )
        
        # 保存设置
        new_settings = {
            "total_capital": total_capital,
            "deepseek_api_key": deepseek_api_key,
            "qwen_api_key": qwen_api_key,
            "kimi_api_key": kimi_api_key,
            "kimi_base_url": kimi_base_url,
            "metaso_api_key": metaso_api_key,
            "metaso_base_url": metaso_base_url,
            "proximity_threshold": proximity_pct,
            "analysis_depth": analysis_depth
        }
        
        # 检测变化
        if (new_settings["total_capital"] != default_capital or
            new_settings["deepseek_api_key"] != settings.get("deepseek_api_key", "") or
            new_settings["qwen_api_key"] != settings.get("qwen_api_key", "") or
            new_settings["kimi_api_key"] != settings.get("kimi_api_key", "") or
            new_settings["kimi_base_url"] != settings.get("kimi_base_url", "https://api.moonshot.cn/v1") or
            new_settings["metaso_api_key"] != settings.get("metaso_api_key", "") or
            new_settings["metaso_base_url"] != settings.get("metaso_base_url", "") or
            new_settings["analysis_depth"] != settings.get("analysis_depth", "标准") or
            abs(new_settings["proximity_threshold"] - settings.get("proximity_threshold", 0.012)) > 0.0001):
            save_settings(new_settings)
        

        
        # 数据管理
        st.markdown("---")
        st.header("数据管理")
        
        # [NEW] 一键刷新实时数据
        if st.sidebar.button("🔄 一键刷新实时数据 (Live)", type="primary"):
            if not selected_labels:
                st.warning("请先添加关注股票")
            else:
                with st.spinner("正在同步交易所实时数据..."):
                    # 1. 更新全市场快照 (Price, Volume, etc.)
                    from utils.data_fetcher import fetch_and_cache_market_snapshot
                    try:
                        fetch_and_cache_market_snapshot()
                    except Exception as e:
                        st.error(f"快照更新失败: {e}")
                    
                    # 2. 更新分钟数据 (Minute Data)
                    progress_bar = st.progress(0)
                    for i, label in enumerate(selected_labels):
                        code_to_sync = label.split(" | ")[0]
                        try:
                            save_minute_data(code_to_sync)
                        except Exception as e:
                            print(f"Failed to sync {code_to_sync}: {e}")
                        progress_bar.progress((i + 1) / len(selected_labels))
                    
                    st.success(f"已更新 {len(selected_labels)} 只股票的实时数据！")
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
        
        if st.sidebar.button("📉 下载/更新历史数据 (History)"):
            if not selected_labels:
                st.warning("请先添加关注股票")
            else:
                with st.spinner("Downloading historical data & Snapshot..."):
                    for label in selected_labels:
                        code_to_sync = label.split(" | ")[0]
                        save_minute_data(code_to_sync)
                        get_stock_fund_flow_history(code_to_sync, force_update=True)
                    st.success(f"已更新 {len(selected_labels)} 只股票的历史数据！")
                    time.sleep(1)
                    st.rerun()
    
    # 返回配置
    return {
        "app_mode": app_mode,
        "selected_labels": selected_labels,
        "total_capital": total_capital,
        "risk_pct": risk_pct,
        "proximity_pct": proximity_pct,
        "deepseek_api_key": deepseek_api_key,
        "qwen_api_key": qwen_api_key,
        "kimi_api_key": kimi_api_key,
        "metaso_api_key": metaso_api_key,
        "metaso_base_url": metaso_base_url,
        "analysis_depth": analysis_depth,
        "active_portfolio": selected_portfolio_id
    }
