# -*- coding: utf-8 -*-
"""
AI 盯盘监控组件
实时展示 AI 的心跳、情绪和决策日志
"""
import streamlit as st
import time
from utils.monitor_logger import get_ai_monitor_state

def render_ai_monitor(code: str):
    """
    渲染 AI 盯盘监控面板
    """
    st.markdown("### 👁️ AI 复盘助手 (Market Review)")
    
    # 获取状态
    state_data = get_ai_monitor_state(code)
    
    if not state_data:
        st.info("AI 尚未启动监控，等待心跳...")
        return
        
    latest, logs = state_data
    
    if not latest:
        st.info("暂无该股票的监控数据")
        return
        
    # 1. 顶部状态栏
    col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
    
    with col1:
        st.metric("上次心跳", latest['timestamp'].split(' ')[1])
    
    with col2:
        decision = latest['decision']
        color = "off"
        if decision == "买入": color = "normal" # Green/Red depends on theme, normal is usually colored
        st.metric("最新决策", decision, delta=None) # Delta could be used for change
        
    with col3:
        sent = latest['sentiment']
        st.metric("当前情绪", sent)
        
    with col4:
        st.caption(f"思考耗时: {latest.get('duration', 'N/A')}")
        st.caption(f"摘要: {latest.get('reason', '')[:20]}...")

    # 2. 动态日志流 (模拟终端效果)
    with st.expander("📟 监控终端日志 (Console Log)", expanded=True):
        log_container = st.container()
        
        # CSS 样式: 黑色背景，绿色字体，终端风格
        st.markdown("""
        <style>
        .console-log {
            background-color: #0e1117;
            color: #00ff41;
            font-family: 'Courier New', Courier, monospace;
            padding: 10px;
            border-radius: 5px;
            height: 150px;
            overflow-y: auto;
            border: 1px solid #303030;
            font-size: 12px;
        }
        .log-entry { return; }
        </style>
        """, unsafe_allow_html=True)
        
        log_html = '<div class="console-log">'
        for log in logs:
            # Highlight current stock
            if f"[{code}]" in log:
                log_html += f'<div class="log-entry" style="color: #00ff41;">> {log}</div>'
            else:
                log_html += f'<div class="log-entry" style="color: #888;">  {log}</div>'
        log_html += '</div>'
        
        st.markdown(log_html, unsafe_allow_html=True)
