# -*- coding: utf-8 -*-
"""
侧边栏组件模块
包含股票选择、交易参数配置、API Key 设置等功能
"""
import streamlit as st
import time

from utils.data_fetcher import get_all_stocks_list, get_stock_fund_flow_history
from utils.storage import save_minute_data
from utils.config import (
    load_selected_stocks, save_selected_stocks,
    get_settings, save_settings
)


def render_sidebar() -> dict:
    """
    渲染侧边栏并返回用户配置
    
    Returns:
        dict: 包含用户选择的股票和配置参数
    """
    # 导航
    st.sidebar.title("🎮 功能导航")
    app_mode = st.sidebar.radio("选择页面", ["实时盯盘", "提示词中心"], index=0)
    
    st.sidebar.markdown("---")
    st.sidebar.header("设置")
    
    # 1. 加载股票列表
    with st.sidebar:
        stock_df = get_all_stocks_list()
        
        if stock_df.empty:
            st.error("加载股票列表失败，请手动刷新。")
        else:
            stock_df['label'] = stock_df['代码'] + " | " + stock_df['名称']
        
        # 2. 加载已保存的配置
        saved_codes = load_selected_stocks()
        default_selections = []
        if not stock_df.empty:
            default_selections = stock_df[stock_df['代码'].isin(saved_codes)]['label'].tolist()
        
        # 3. 股票选择器
        selected_labels = st.multiselect(
            "选择股票 (最多5只)",
            options=stock_df['label'] if not stock_df.empty else [],
            default=default_selections,
            max_selections=5,
            help="您最多只能选择5只股票进行监控。"
        )
        
        # 保存选择
        current_codes = [label.split(" | ")[0] for label in selected_labels]
        if set(current_codes) != set(saved_codes):
            save_selected_stocks(current_codes)
        
        # 4. 设置参数
        settings = get_settings()
        
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
        
        # Gemini
        gemini_api_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Google Gemini API Key",
            key="input_gemini"
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
        
        # Metaso 高级设置
        with st.expander("高级设置 (Endpoint)", expanded=False):
            if "input_metaso_url" not in st.session_state:
                st.session_state.input_metaso_url = settings.get("metaso_base_url", "https://metaso.cn/api/v1")
            
            metaso_base_url = st.text_input(
                "API Base URL",
                value=st.session_state.input_metaso_url,
                help="默认: https://metaso.cn/api/v1",
                key="input_metaso_url"
            )
        
        # 保存设置
        new_settings = {
            "total_capital": total_capital,
            "deepseek_api_key": deepseek_api_key,
            "gemini_api_key": gemini_api_key,
            "metaso_api_key": metaso_api_key,
            "metaso_base_url": metaso_base_url,
            "proximity_threshold": proximity_pct
        }
        
        # 检测变化
        if (new_settings["total_capital"] != default_capital or
            new_settings["deepseek_api_key"] != settings.get("deepseek_api_key", "") or
            new_settings["gemini_api_key"] != settings.get("gemini_api_key", "") or
            new_settings["metaso_api_key"] != settings.get("metaso_api_key", "") or
            new_settings["metaso_base_url"] != settings.get("metaso_base_url", "") or
            abs(new_settings["proximity_threshold"] - settings.get("proximity_threshold", 0.012)) > 0.0001):
            save_settings(new_settings)
        
        # 刷新设置
        auto_refresh = st.checkbox("自动刷新", value=False)
        refresh_rate = st.slider("刷新间隔 (秒)", 5, 60, 10)
        
        # 数据管理
        st.markdown("---")
        st.header("数据管理")
        
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
        "gemini_api_key": gemini_api_key,
        "metaso_api_key": metaso_api_key,
        "metaso_base_url": metaso_base_url,
        "auto_refresh": auto_refresh,
        "refresh_rate": refresh_rate
    }
