# -*- coding: utf-8 -*-
import streamlit as st
import time
from utils.intel_manager import get_claims, add_claims, delete_claim, mark_claims_distinct
from utils.ai_parser import parse_metaso_report, find_duplicate_candidates
from utils.researcher import ask_metaso_research_loop
from utils.researcher import ask_metaso_research_loop
from utils.config import load_config
from utils.data_fetcher import get_stock_news_raw
from utils.intelligence_processor import summarize_intelligence
from utils.qwen_agent import search_with_qwen

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
        col_top1, col_top2, col_top3 = st.columns([0.33, 0.33, 0.33])

        
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

        # 2. Qwen Search Button [NEW]
        if col_top2.button("🐶 Qwen 全网检索", key=f"btn_qwen_{code}", use_container_width=True):
            if not deepseek_api_key and not settings.get("qwen_api_key"): 
                st.warning("请设置 Qwen API Key (DashScope)")
            else:
                 # Try to get DashScope key specifically if separate, or use same one
                dashscope_key = settings.get("dashscope_api_key") or settings.get("qwen_api_key") or deepseek_api_key
                
                with st.spinner(f"🐶 Qwen 正在全网检索 {name} ..."):
                     # Construct query
                    query = f"A股 {name} ({code}) 最新重大利好与利空消息 业绩 研报"
                    
                    new_claims = search_with_qwen(dashscope_key, query)
                    if new_claims:
                        add_claims(code, new_claims, source="Qwen Search")
                        st.success(f"Qwen 搜寻到 {len(new_claims)} 条新情报！")
                    else:
                        st.warning("Qwen 未搜寻到有效情报或接口异常。")
                    time.sleep(1)
                    st.rerun()

        # 3. Dedupe Button
        if f"dedupe_results_{code}" not in st.session_state:
            st.session_state[f"dedupe_results_{code}"] = None
        
        current_claims = get_claims(code)
        if col_top3.button("🧹 扫描重复并清理", key=f"btn_dedupe_{code}", use_container_width=True):
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
                            st.text_area("内容", item_obj['content'], height=250, disabled=True, key=f"txt_{code}_{g_idx}_{item_obj['id']}")
                            if st.button(f"✅ 保留此条 (合并)", key=f"keep_{code}_{g_idx}_{item_obj['id']}"):
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
        
        # [NEW] Manual Input Section
        with st.expander("📝 手动录入重要情报 (Manual Input)", expanded=True):
            user_intel = st.text_area(
                "请输入您获得的情报 (将作为最高优先级传给AI):", 
                height=100, 
                key=f"manual_intel_{code}",
                help="此处输入的信息会被标记为【UserManual】来源，并在DeepSeek提示词中置顶显示。"
            )
            if st.button("💾 保存情报", key=f"btn_save_manual_{code}"):
                if not user_intel.strip():
                    st.warning("内容不能为空")
                else:
                    add_claims(code, [user_intel.strip()], source="UserManual")
                    st.success("已保存！该情报将作为核心信息传给AI。")
                    time.sleep(1)
                    st.rerun()


        st.markdown("---")
        
        # [NEW] Real-time News Section (EastMoney)
        with st.expander("🌐 实时资讯 (EastMoney/Sina)", expanded=False):
            n_col1, n_col2 = st.columns([0.3, 0.7])
            with n_col1:
                if st.button("🔄 刷新资讯", key=f"btn_refresh_news_{code}"):
                    get_stock_news_raw.clear()
                    st.toast("已清除资讯缓存，正在重新抓取...")
                    time.sleep(0.5)
                    st.rerun()
            with n_col2:
                if st.button("⚡ AI 提炼入库 (Summarize & Save)", key=f"btn_sum_news_{code}", help="调用 DeepSeek 阅读最新20条新闻，生成摘要并存入情报库"):
                    if not deepseek_api_key:
                        st.error("请先设置 DeepSeek API Key")
                    else:
                        with st.spinner("🤖 正在阅读并提炼最近20条新闻..."):
                            try:
                                raw_news = get_stock_news_raw(code, n=20)
                                if raw_news:
                                    summary = summarize_intelligence(deepseek_api_key, raw_news, name)
                                    if summary:
                                        # Save as a single consolidated claim
                                        add_claims(code, [summary], source="EastMoney AI摘要")
                                        st.success("✅ 已提炼并存入情报库！")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.warning("AI 未生成有效摘要")
                                else:
                                    st.warning("无新闻可提炼")
                            except Exception as e:
                                st.error(f"提炼失败: {e}")
                
            try:
                news_items = get_stock_news_raw(code, n=10)
                if not news_items:
                    st.info("暂无最新资讯。")
                else:
                    for news in news_items:
                        n_title = news.get("title", "无标题")
                        n_date = news.get("date", "")
                        n_url = news.get("url", "")
                        
                        # Format
                        st.markdown(f"**[{n_date}]** [{n_title}]({n_url})")
            except Exception as e:
                st.error(f"资讯获取失败: {e}")

        st.markdown("---")
        st.markdown("---")
        current_claims = get_claims(code)
        if not current_claims:
            st.info("暂无收回的情报。请点击上方按钮进行抓取。")
        else:
            # Group claims by source
            manual_claims = []
            ai_claims = []
            search_claims = []
            
            for item in current_claims:
                source = item.get('source', '')
                if source == 'UserManual':
                    manual_claims.append(item)
                elif source == 'EastMoney AI摘要':
                    ai_claims.append(item)
                else:
                    search_claims.append(item)
            
            # Create Tabs
            tab_u, tab_a, tab_s = st.tabs([
                f"🚨 核心情报 ({len(manual_claims)})", 
                f"🤖 AI 研报 ({len(ai_claims)})", 
                f"🔍 深度搜索 ({len(search_claims)})"
            ])
            
            def render_claim_item(item):
                status_map = {
                    "verified": "🟢",
                    "disputed": "🟠",
                    "false_info": "❌",
                    "pending": "⚪"
                }
                status_icon = status_map.get(item.get('status', 'pending'), "⚪")
                
                # Special icon for manual
                src = item.get('source', '')
                if src == 'UserManual':
                    status_icon = "🚨"
                elif src == 'Qwen Search':
                     status_icon = "🐶"
                elif src == 'Metaso':
                     status_icon = "Ⓜ️"

                content_display = item['content']
                if item.get('status') == 'false_info':
                    content_display = f"~~{content_display}~~ (已证伪)"
                
                with st.container(border=True):
                    col_main, col_del = st.columns([0.9, 0.1])
                    with col_main:
                        st.markdown(f"**{status_icon} [{item['timestamp']}]**")
                        st.caption(f"来源: {src}")
                        st.code(content_display, language=None, wrap_lines=True)
                        if item.get('note'):
                            st.info(f"备注: {item['note']}")
                    with col_del:
                        if st.button("🗑️", key=f"del_{item['id']}", help="删除此条情报"):
                            delete_claim(code, item['id'])
                            st.rerun()

            with tab_u:
                if manual_claims:
                    for item in manual_claims:
                        render_claim_item(item)
                else:
                    st.info("暂无用户录入的核心情报")

            with tab_a:
                if ai_claims:
                    for item in ai_claims:
                        render_claim_item(item)
                else:
                    st.info("暂无 AI 生成的研报摘要")

            with tab_s:
                if search_claims:
                    for item in search_claims:
                        render_claim_item(item)
                else:
                    st.info("暂无深度搜索情报")
