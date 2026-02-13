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
    db_remove_watchlist
)


def render_sidebar() -> dict:
    """
    渲染侧边栏并返回用户配置
    
    Returns:
        dict: 包含用户选择的股票和配置参数
    """
    # 导航
    st.sidebar.title("🎮 功能导航")
    app_mode = st.sidebar.radio("选择页面", ["复盘与预判", "操盘记录", "提示词中心", "策略实验室"], index=0)
    
    st.sidebar.markdown("---")
    
    # [NEW] Quick Trade (Unified Entry)
    with st.sidebar.expander("⚡️ 快速交易 (Quick Trade)", expanded=True):
        trade_cmd = st.text_input("交易指令", placeholder="例如: 600076 4.2买入 1000", key="quick_trade_input")
        
        if st.button("执行交易", type="primary", key="btn_exec_trade"):
            if not trade_cmd.strip():
                st.error("请输入交易指令")
            else:
                from utils.text_parser import parse_trade_command
                from utils.trade_manager import execute_trade
                
                # 1. Parse
                parsed = parse_trade_command(trade_cmd)
                if not parsed["valid"]:
                    st.error(f"解析失败: {parsed['error']}")
                else:
                    # 2. Confirm (Auto-execute for now, or use Session STate logic for double confirm? 
                    # User requested 'Input -> System extracts -> Updates'. Let's do direct for speed, maybe toast.)
                    
                    code = parsed["symbol"]
                    action = parsed["action"] # buy/sell
                    price = parsed["price"]
                    qty = parsed["quantity"]
                    
                    # 3. Execute
                    with st.spinner(f"正在执行: {action} {code} {qty}股 @ {price}..."):
                        res = execute_trade(code, action, price, qty, note="快速交易")
                        
                    if res["success"]:
                        st.success(res["message"])
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(res["message"])

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
        
        # Qwen (Tongyi Qianwen)
        if "input_qwen" not in st.session_state:
            st.session_state.input_qwen = settings.get("qwen_api_key", "")
            
        qwen_api_key = st.text_input(
            "Qwen API Key (DashScope)",
            type="password",
            help="阿里云 DashScope API Key，用于红队审查",
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
            "Kimi API Key (Moonshot)",
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
        
        # 刷新设置
        auto_refresh = st.checkbox("自动刷新", value=False)
        refresh_rate = st.slider("刷新间隔 (秒)", 30, 300, 60, help="建议保持 60秒以上，以避免触发数据源流控限制。")
        
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
        "auto_refresh": auto_refresh,
        "refresh_rate": refresh_rate
    }
