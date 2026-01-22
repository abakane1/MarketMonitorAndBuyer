# -*- coding: utf-8 -*-
import streamlit as st
import time
from utils.intel_manager import get_claims, add_claims, delete_claim, mark_claims_distinct
from utils.ai_parser import parse_metaso_report, find_duplicate_candidates
from utils.researcher import ask_metaso_research_loop
from utils.config import load_config

def render_intel_hub(code: str, name: str, price: float, avg_cost: float, shares_held: int, strat_res: dict, total_capital: float, current_alloc: float):
    """
    渲染股票情报数据库组件 (Intelligence Hub)
    """
    settings = load_config().get("settings", {})
    metaso_api_key = st.session_state.get("input_metaso_key", "")
    deepseek_api_key = st.session_state.get("input_apikey", "")
    metaso_base_url = settings.get("metaso_base_url", "https://metaso.cn/api/v1")
    
    with st.expander("🗃️ 股票情报数据库 (Intelligence Hub)", expanded=False):
        # --- Top Action Buttons ---
        col_top1, col_top2 = st.columns([0.5, 0.5])
        
        # 1. Metaso Search Button
        if col_top1.button("🔍 秘塔深度搜索", key=f"btn_metaso_{code}", use_container_width=True):
            if not metaso_api_key or not deepseek_api_key:
                st.warning("请在侧边栏设置 Metaso API Key 和 DeepSeek API Key")
            else:
                with st.spinner(f"🔍 秘塔正在检索 {name} 的最新情报..."):
                    prompts = load_config().get("prompts", {})
                    context = {
                        "code": code, "name": name, "price": price, "cost": avg_cost, 
                        "current_shares": shares_held, "support": strat_res.get('support'), 
                        "resistance": strat_res.get('resistance'), "signal": strat_res.get('signal'),
                        "reason": strat_res.get('reason'), "capital_allocation": current_alloc,
                        "total_capital": total_capital
                    }
                    
                    research_report = ask_metaso_research_loop(
                        metaso_api_key, metaso_base_url, deepseek_api_key, context, 
                        base_query_template=prompts.get("metaso_query", ""),
                        existing_claims=get_claims(code),
                        metaso_parser_template=prompts.get("metaso_parser", "")
                    )
                    
                    # Manual Parse call (ask_metaso_research_loop usually returns raw text, we parse it)
                    # Note: ask_metaso_research_loop inside researcher.py MIGHT already parse? 
                    # Let's check imports. In main.py it calls ask_metaso_research_loop THEN parse_metaso_report.
                    # Yes.
                    
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
                with st.spinner("正在对比语义分析重复项 (DeepSeek)..."):
                    if not deepseek_api_key:
                        st.error("请先设置 DeepSeek API Key")
                    else:
                        dupe_groups = find_duplicate_candidates(deepseek_api_key, current_claims)
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
