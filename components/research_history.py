# -*- coding: utf-8 -*-
"""
Research History Component - 历史研报记录展示组件 v2.1
重构目标: 清晰展示每一步的提示词、思考过程、决策内容
"""

import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from utils.research_report import ResearchReport, StepRecord
from utils.storage import load_structured_research_reports
from utils.database import db_get_history
from utils.time_utils import get_target_date_for_strategy


STEP_CONFIG = {
    "draft": {
        "icon": "🧠",
        "name": "蓝军初稿",
        "color": "blue",
        "description": "蓝军主帅基于多维数据生成初始策略草案"
    },
    "audit1": {
        "icon": "🛡️",
        "name": "红军初审",
        "color": "red",
        "description": "红军审计师进行深度风险审查与数据验证"
    },
    "refine": {
        "icon": "🔄",
        "name": "蓝军优化",
        "color": "blue",
        "description": "蓝军根据审计意见进行策略优化与修正"
    },
    "audit2": {
        "icon": "⚖️",
        "name": "红军终审",
        "color": "red",
        "description": "红军进行最终裁决，评估优化后的策略"
    },
    "final": {
        "icon": "🏁",
        "name": "最终执行令",
        "color": "green",
        "description": "蓝军生成简洁明确的最终执行指令"
    }
}


def extract_decision_summary(content: str) -> Dict[str, str]:
    """从内容中提取决策摘要"""
    summary = {
        "direction": "N/A",
        "price": "N/A",
        "shares": "N/A",
        "stop_loss": "N/A",
        "take_profit": "N/A"
    }
    
    if not content:
        return summary
    
    # 提取方向
    direction_patterns = [
        r"方向[:：]\s*(\S+)",
        r"【(买入|卖出|观望|持有)】",
        r"决策[:：]\s*(\S+)"
    ]
    for pattern in direction_patterns:
        match = re.search(pattern, content)
        if match:
            summary["direction"] = match.group(1).strip()
            break
    
    # 提取价格
    price_patterns = [
        r"建议价格[:：]\s*(\S+)",
        r"入场[:：]\s*(\S+)",
        r"价格[:：]\s*(\S+)"
    ]
    for pattern in price_patterns:
        match = re.search(pattern, content)
        if match:
            summary["price"] = match.group(1).strip()
            break
    
    # 提取股数
    shares_patterns = [
        r"建议股数[:：]\s*(\S+)",
        r"仓位[:：]\s*(\S+)",
        r"股数[:：]\s*(\S+)"
    ]
    for pattern in shares_patterns:
        match = re.search(pattern, content)
        if match:
            summary["shares"] = match.group(1).strip()
            break
    
    # 提取止损
    sl_patterns = [
        r"止损价格[:：]\s*(\S+)",
        r"止损[:：]\s*(\S+)"
    ]
    for pattern in sl_patterns:
        match = re.search(pattern, content)
        if match:
            summary["stop_loss"] = match.group(1).strip()
            break
    
    # 提取止盈
    tp_patterns = [
        r"止盈价格[:：]\s*(\S+)",
        r"止盈[:：]\s*(\S+)"
    ]
    for pattern in tp_patterns:
        match = re.search(pattern, content)
        if match:
            summary["take_profit"] = match.group(1).strip()
            break
    
    return summary


def render_step_card(step: StepRecord, expanded: bool = False):
    """渲染单步卡片"""
    config = STEP_CONFIG.get(step.step_type, {
        "icon": "📝",
        "name": step.role or "未知步骤",
        "color": "gray",
        "description": ""
    })
    
    icon = config["icon"]
    name = config["name"]
    color = config["color"]
    
    # 标题样式
    title_html = f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: linear-gradient(90deg, {color}22, transparent);
        border-left: 4px solid {color};
        border-radius: 4px;
        margin-bottom: 8px;
    ">
        <span style="font-size: 20px;">{icon}</span>
        <div>
            <div style="font-weight: 600; color: {color};">Step {step.step}: {name}</div>
            <div style="font-size: 12px; color: #666;">{step.model} | {step.timestamp or 'N/A'}</div>
        </div>
    </div>
    """
    
    with st.container():
        st.markdown(title_html, unsafe_allow_html=True)
        
        # 决策摘要 (如果有)
        if step.content:
            decision = extract_decision_summary(step.content)
            if decision["direction"] != "N/A":
                cols = st.columns(5)
                with cols[0]:
                    st.markdown(f"**方向**: {decision['direction']}")
                with cols[1]:
                    st.markdown(f"**价格**: {decision['price']}")
                with cols[2]:
                    st.markdown(f"**股数**: {decision['shares']}")
                with cols[3]:
                    st.markdown(f"**止损**: {decision['stop_loss']}")
                with cols[4]:
                    st.markdown(f"**止盈**: {decision['take_profit']}")
        
        # 三个Tab: 决策内容 | 思考过程 | 提示词
        tab_content, tab_reasoning, tab_prompt = st.tabs(["📝 决策内容", "💭 思考过程", "🔧 提示词"])
        
        with tab_content:
            if step.content:
                st.markdown(step.content)
            else:
                st.info("暂无决策内容")
        
        with tab_reasoning:
            if step.reasoning:
                st.markdown(step.reasoning)
            else:
                st.caption("此步骤未提供思考过程")
        
        with tab_prompt:
            if step.system_prompt:
                with st.expander("System Prompt", expanded=False):
                    st.code(step.system_prompt, language="text")
            
            if step.user_prompt:
                with st.expander("User Prompt", expanded=False):
                    st.code(step.user_prompt, language="text")
            
            if not step.system_prompt and not step.user_prompt:
                st.caption("此步骤未保存提示词")
        
        st.markdown("---")


def render_research_history(code: str):
    """
    渲染历史研报记录主组件
    
    Args:
        code: 股票代码
    """
    st.markdown("---")
    
    # 加载数据
    try:
        reports = load_structured_research_reports(code)
    except Exception as e:
        st.error(f"加载研报记录失败: {e}")
        reports = []
    
    if not reports:
        st.info("📭 暂无历史研报记录")
        return
    
    # 准备汇总表格数据
    trades = db_get_history(code)
    real_trades = [t for t in trades if t['type'] in ['buy', 'sell'] and t.get('amount', 0) > 0]
    
    history_data = []
    report_options = {}
    
    for report in reports:
        ts = report.timestamp
        dt_ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        
        # 确定适用日期
        target_date = get_target_date_for_strategy(dt_ts)
        
        # 查找关联的交易
        next_report_time = None
        for r in reports:
            if r.timestamp > ts:
                next_report_time = r.timestamp
                break
        
        end_time = next_report_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        matched_tx = []
        for t in real_trades:
            t_ts = t['timestamp']
            if ts <= t_ts < end_time:
                action_str = "买" if t['type'] == 'buy' else "卖"
                matched_tx.append(f"{action_str} {int(t['amount'])}@{t['price']}")
        
        tx_str = "; ".join(matched_tx) if matched_tx else "-"
        
        # 提取最终决策方向
        final_step = report.get_step("final") or (report.steps[-1] if report.steps else None)
        if final_step:
            decision = extract_decision_summary(final_step.content)
            signal_show = decision["direction"]
        else:
            signal_show = "N/A"
        
        # 确定类型标签
        hour = dt_ts.hour
        if hour >= 15 or hour < 9:
            tag = "盘前"
        else:
            tag = "盘中"
        
        history_data.append({
            "生成时间": ts,
            "适用日期": target_date,
            "类型": tag,
            "AI建议": signal_show,
            "实际执行": tx_str,
            "raw_report": report
        })
        
        label = f"{ts} | {signal_show} | Exec: {tx_str}"
        report_options[label] = report
    
    # 显示汇总表格
    st.caption("📊 策略与执行追踪")
    df_hist = pd.DataFrame(history_data)
    st.dataframe(
        df_hist[['适用日期', '类型', 'AI建议', '实际执行', '生成时间']], 
        hide_index=True,
        use_container_width=True,
        column_config={
            "适用日期": st.column_config.TextColumn("适用日期", width="small"),
            "类型": st.column_config.TextColumn("类型", width="small"),
            "生成时间": st.column_config.TextColumn("生成时间", width="medium"),
            "实际执行": st.column_config.TextColumn("实际执行", width="large"),
            "AI建议": st.column_config.TextColumn("AI建议", width="small"),
        }
    )
    
    # 详情选择
    st.divider()
    selected_label = st.selectbox(
        "🔍 查看详情 (选择研报)",
        options=list(report_options.keys()),
        key=f"hist_sel_{code}"
    )
    
    if selected_label:
        report = report_options[selected_label]
        
        # 找到关联执行
        linked_tx = "N/A"
        for item in history_data:
            if item["raw_report"] == report:
                linked_tx = item["实际执行"]
                break
        
        # 头部信息
        st.markdown(f"### 🗓️ {report.timestamp}")
        
        if linked_tx != "-":
            st.info(f"⚡ **关联执行**: {linked_tx}")
        
        # 最终决策展示
        final_step = report.get_step("final") or (report.steps[-1] if report.steps else None)
        
        # 如果没有找到 final_step 但有 raw_result，从 raw_result 提取
        if not final_step and report.raw_result:
            # 从旧格式解析最终决策
            from utils.research_report import ResearchReport
            step_contents = ResearchReport._parse_legacy_result(report.raw_result)
            final_content = step_contents.get('final', report.raw_result[:2000])  # 限制长度
            
            # 创建一个临时的 final_step 用于显示 (需要包含所有 StepRecord 的属性)
            final_step = type('obj', (object,), {
                'step': 5,
                'step_type': 'final',
                'role': '最终决策',
                'model': 'DeepSeek',
                'system_prompt': '',
                'user_prompt': report.raw_prompt or "",
                'reasoning': report.raw_reasoning or "",
                'content': final_content,
                'decision': None,
                'timestamp': report.timestamp
            })()
        
        if final_step:
            decision = extract_decision_summary(final_step.content if hasattr(final_step, 'content') else str(final_step))
            
            # 决策卡片
            d_color = "gray"
            if decision["direction"] in ["买入", "做多"]:
                d_color = "green"
            elif decision["direction"] in ["卖出", "做空"]:
                d_color = "red"
            
            st.markdown(f"""
            <div style="
                padding: 16px;
                background: {d_color}11;
                border: 1px solid {d_color}44;
                border-radius: 8px;
                margin: 16px 0;
            ">
                <div style="font-size: 14px; color: #666; margin-bottom: 8px;">最终决策</div>
                <div style="display: flex; gap: 24px; flex-wrap: wrap;">
                    <div><span style="color: {d_color}; font-size: 24px; font-weight: bold;">{decision['direction']}</span></div>
                    <div><span style="color: #666;">价格:</span> <b>{decision['price']}</b></div>
                    <div><span style="color: #666;">股数:</span> <b>{decision['shares']}</b></div>
                    <div><span style="color: #666;">止损:</span> <b style="color: red;">{decision['stop_loss']}</b></div>
                    <div><span style="color: #666;">止盈:</span> <b style="color: green;">{decision['take_profit']}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # 步骤展示模式选择
        view_mode = st.radio(
            "📑 展示模式",
            ["分步详情 (推荐)", "全流程对比", "原始数据"],
            horizontal=True,
            key=f"view_mode_{code}"
        )
        
        if view_mode == "分步详情 (推荐)":
            # 按步骤展示，每个步骤一个卡片
            if report.steps:
                for step in report.steps:
                    render_step_card(step)
            elif final_step:
                # 旧数据，只有最终决策，显示一个简化卡片
                render_step_card(final_step)
            else:
                st.info("📭 暂无详细步骤数据")
        
        elif view_mode == "全流程对比":
            # 横向对比各步骤的决策变化
            st.info("📊 对比各步骤的决策变化")
            
            comparison_data = []
            for step in report.steps:
                decision = extract_decision_summary(step.content)
                comparison_data.append({
                    "步骤": f"{STEP_CONFIG.get(step.step_type, {}).get('icon', '📝')} {step.role}",
                    "方向": decision["direction"],
                    "价格": decision["price"],
                    "股数": decision["shares"],
                    "模型": step.model
                })
            
            if comparison_data:
                df_comp = pd.DataFrame(comparison_data)
                st.dataframe(df_comp, hide_index=True, use_container_width=True)
            
            # 显示思考过程的演变
            st.markdown("#### 💭 思考过程演变")
            for step in report.steps:
                if step.reasoning:
                    with st.expander(f"{STEP_CONFIG.get(step.step_type, {}).get('icon', '📝')} {step.role} 的思考", expanded=False):
                        st.markdown(step.reasoning)
        
        else:  # 原始数据
            # 显示原始字符串 (兼容旧数据)
            if report.raw_result:
                with st.expander("原始 Result 字符串", expanded=False):
                    st.code(report.raw_result, language="text")
            
            if report.raw_prompt:
                with st.expander("原始 Prompt 字符串", expanded=False):
                    st.code(report.raw_prompt, language="text")
            
            # 显示JSON结构
            with st.expander("结构化数据 (JSON)", expanded=False):
                st.json(report.to_dict())
        
        # 删除按钮
        st.markdown("---")
        if st.button("🗑️ 删除此记录", key=f"del_rsch_{code}_{report.timestamp}"):
            from utils.storage import delete_production_log
            if delete_production_log(code, report.timestamp):
                st.success("已删除")
                st.rerun()
