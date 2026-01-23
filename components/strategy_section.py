# -*- coding: utf-8 -*-
import streamlit as st
import time
from utils.strategy import analyze_volume_profile_strategy
from utils.storage import get_volume_profile, get_latest_strategy_log, save_research_log, load_research_log, delete_research_log
from utils.ai_parser import extract_bracket_content
from utils.config import load_config, get_allocation, set_allocation
from utils.monitor_logger import log_ai_heartbeat
from utils.database import db_get_history

import pandas as pd

import re
import datetime

def render_strategy_section(code: str, name: str, price: float, shares_held: int, avg_cost: float, total_capital: float, risk_pct: float, proximity_pct: float, pre_close: float = 0.0):
    """
    渲染策略分析区域 (算法 + AI)
    """
    
    # 1. Capital Allocation UI
    current_alloc = get_allocation(code)
    eff_capital = total_capital # Default
    
    with st.expander("⚙️ 资金配置 (Capital Allocation)", expanded=False):
        new_alloc = st.number_input(
            f"本股资金限额 (0表示使用总资金)",
            value=float(current_alloc),
            min_value=0.0,
            step=10000.0,
            format="%.0f",
            key=f"alloc_{code}",
            help="限制该股票的最大持仓市值。策略将利用此数值计算建议仓位。"
        )
        if st.button("保存限额", key=f"save_{code}"):
            set_allocation(code, new_alloc)
            st.success(f"已保存! 本股资金限额: {new_alloc}")
            time.sleep(0.5)
            st.rerun()
            
        st.markdown("---")
        # Base Position UI
        from utils.config import set_base_shares
        from utils.database import db_get_position
        # Use DB
        curr_pos = db_get_position(code)
        curr_base = curr_pos.get("base_shares", 0)
        
        new_base = st.number_input(
            f"🔒 底仓锁定 (Base Position)",
            value=int(curr_base),
            min_value=0,
            step=100,
            key=f"base_in_{code}",
            help="设置长期持有的底仓数量。AI 将被禁止卖出这部分筹码。"
        )
        if st.button("保存底仓", key=f"save_base_{code}"):
            set_base_shares(code, new_base)
            st.success(f"已锁定底仓: {new_base} 股")
            time.sleep(0.5)
            st.rerun()
            
    if new_alloc > 0:
        eff_capital = new_alloc

    # Calculate Strategy
    vol_profile_for_strat, vol_meta = get_volume_profile(code)
    strat_res = analyze_volume_profile_strategy(
        price, 
        vol_profile_for_strat, 
        eff_capital, 
        risk_pct, 
        current_shares=shares_held,
        proximity_threshold=proximity_pct
    )
    
    # --- Algorithm Section (Simplified) ---
    with st.expander("⚙️ 算法建议 (Algorithm)", expanded=False):
        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        
        signal = strat_res.get('signal')
        color = "grey"
        if signal == "买入": color = "green"
        if signal == "卖出": color = "red"
        
        s_col1.markdown(f"**建议方向**: :{color}[{signal}]")
        s_col2.metric("建议股数", strat_res.get('quantity', 0))
        
        sl_val = strat_res.get('stop_loss', 0)
        sl_label = "止损参考"
        if shares_held > 0 and sl_val > avg_cost: sl_label = "利润保护"
        s_col3.metric(sl_label, sl_val)
        
        tp_val = strat_res.get('take_profit', 'N/A')
        s_col4.metric("止盈参考", tp_val)
        
        st.caption(f"💡 逻辑依据: {strat_res.get('reason')}")
        st.caption(f"📊 支撑: {strat_res.get('support')} | 阻力: {strat_res.get('resistance')}")


    # --- AI Section (Elevated) ---
    with st.expander("🧠 AI 深度研判 (AI Analysis)", expanded=False):
        st.markdown("---")
        
        # Check for Pending Draft
        pending_key = f"pending_ai_result_{code}"
        ai_strat_log = None
        
        if pending_key in st.session_state:
            # We have a draft, show it!
            ai_strat_log = st.session_state[pending_key]
            st.warning("⚠️ 新生成策略待确认 (Draft Mode)")
            
            # Action Bar
            col_conf, col_disc = st.columns(2)
            with col_conf:
                if st.button("✅ 确认入库 (Confirm)", key=f"btn_confirm_{code}", use_container_width=True):
                    # Save to disk
                    save_research_log(
                        code, 
                        ai_strat_log['prompt'], 
                        f"{ai_strat_log.get('tag', '')} {ai_strat_log['result']}", 
                        ai_strat_log['reasoning']
                    )
                    # Clear draft
                    del st.session_state[pending_key]
                    st.success("策略已入库！")
                    time.sleep(0.5)
                    st.rerun()
                    
            with col_disc:
                if st.button("🗑️ 放弃 (Discard)", key=f"btn_discard_{code}", use_container_width=True):
                    # Clear draft
                    del st.session_state[pending_key]
                    st.info("策略已放弃")
                    time.sleep(0.5)
                    st.rerun()
            
            st.markdown("---")
        
        # If no draft, load from disk
        if not ai_strat_log:
             ai_strat_log = get_latest_strategy_log(code)
        
        # DeepSeek Config
        settings = load_config().get("settings", {})
        deepseek_api_key = st.session_state.get("input_apikey", "")
        
        if ai_strat_log:
            content = ai_strat_log['result']
            reasoning = ai_strat_log.get('reasoning', '')
            ts = ai_strat_log['timestamp'][5:16]
            st.caption(f"📅 最后生成: {ts}")
            
            # --- Simple Parser (Reuse original logic) ---
            ai_signal = "N/A"
            pos_txt = "N/A"
            stop_loss_txt = "N/A"
            entry_txt = "N/A"
            take_profit_txt = "N/A"

            block_match = re.search(r"【决策摘要】(.*)", content, re.DOTALL)
            if block_match:
                block_content = block_match.group(1)
                s_match = re.search(r"方向:\s*(\[)?(.*?)(])?\n", block_content)
                if not s_match: s_match = re.search(r"方向:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if s_match: ai_signal = s_match.group(2).replace("[","").replace("]","").strip()
                
                e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?\n", block_content)
                if not e_match: e_match = re.search(r"建议价格:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if e_match: entry_txt = e_match.group(2).replace("[","").replace("]","").strip()
                    
                p_match = re.search(r"(?:建议|目标)?(?:股数|仓位):\s*(\[)?(.*?)(])?(?:\n|$)", block_content)
                if p_match: pos_txt = p_match.group(2).replace("[","").replace("]","").strip()
                    
                sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                if not sl_match: sl_match = re.search(r"止损(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if sl_match: stop_loss_txt = sl_match.group(3).replace("[","").replace("]","").strip()
                    
                tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?\n", block_content)
                if not tp_match: tp_match = re.search(r"(止盈|目标)(价格)?:\s*(\[)?(.*?)(])?$", block_content, re.MULTILINE)
                if tp_match: take_profit_txt = tp_match.group(4).replace("[","").replace("]","").strip()

            else:
                signal_match = re.search(r"【(买入|卖出|做空|观望|持有)】", content)
                ai_signal = signal_match.group(1) if signal_match else "N/A"
                lines = content.split('\n')
                for line in lines:
                    if "止损" in line: stop_loss_txt = line.split(":")[-1].strip().replace("元","")[:10]
                    if "止盈" in line or "目标" in line: take_profit_txt = line.split(":")[-1].strip().replace("元","")[:10]
                    if "股数" in line or "仓位" in line: pos_txt = line.split(":")[-1].strip()[:10]
            
            if "N/A" in ai_signal and "观望" in content: ai_signal = "观望"
            
            ai_col1, ai_col2, ai_col3, ai_col4, ai_col5 = st.columns(5)
            s_color = "grey"
            if ai_signal in ["买入", "做多"]: s_color = "green"
            if ai_signal in ["卖出", "做空"]: s_color = "red"
            pos_val, pos_note = extract_bracket_content(pos_txt if pos_txt != "N/A" else "--")
            sl_val, sl_note = extract_bracket_content(stop_loss_txt if stop_loss_txt != "N/A" else "--")
            tp_val, tp_note = extract_bracket_content(take_profit_txt if take_profit_txt != "N/A" else "--")
            entry_val, entry_note = extract_bracket_content(entry_txt if entry_txt != "N/A" else "--")

            ai_col1.markdown(f"**AI建议**: :{s_color}[{ai_signal}]")
            
            ai_col2.metric("建议价格", entry_val)
            if entry_note: ai_col2.caption(f"({entry_note})")
            
            ai_col3.metric("建议股数", pos_val)
            if pos_note: ai_col3.caption(f"({pos_note})")
            
            ai_col4.metric("止损参考", sl_val)
            if sl_note: ai_col4.caption(f"({sl_note})")
            
            ai_col5.metric("止盈参考", tp_val)
            if tp_note: ai_col5.caption(f"({tp_note})")
            
            with st.expander("📄 查看完整策略报告", expanded=False):
                st.markdown(content)
                if reasoning:
                    st.divider()
                    st.caption("AI 思考过程 (Chain of Thought)")
                    st.text(reasoning)

        else:
            st.info("👋 暂无 AI 独立策略记录。")

        st.markdown("---")
        # Control Buttons
        from utils.time_utils import is_trading_time
        market_open = is_trading_time()
        
        # Display Base Position Info (if configured)
        from utils.database import db_get_position
        curr_pos_ui = db_get_position(code)
        base_s_ui = curr_pos_ui.get("base_shares", 0)
        if base_s_ui > 0:
             tradable_s_ui = max(0, shares_held - base_s_ui)
             st.info(f"🛡️ **风控护盾已激活** | 总持仓: {shares_held} | 🔒 底仓(Locked): **{base_s_ui}** | 🔄 可交易: **{tradable_s_ui}**")
        
        c_p1, c_p2 = st.columns(2)
        start_pre = False
        start_intra = False
        
        with c_p1:
            if st.button("💡 生成盘前策略 (Pre-market)", key=f"btn_pre_{code}", use_container_width=True):
                target_suffix_key = "deepseek_new_strategy_suffix"
                start_pre = True
        
        with c_p2:
            if st.button("⚡ 生成盘中对策 (Intra-day)", key=f"btn_intra_{code}", use_container_width=True):
                target_suffix_key = "deepseek_intraday_suffix"
                start_intra = True

        if start_pre or start_intra:
            warning_msg = None
            if start_pre and market_open:
                warning_msg = "⚠️ 警告: 市场正在交易中，您选择了【盘前策略】。盘前计划可能不包含最新的盘口特征。"
            if start_intra and not market_open:
                warning_msg = "⚠️ 警告: 市场已休市或未开盘，您选择了【盘中对策】。缺乏实时盘口数据可能导致AI判断失真。"
                 
            prompts = load_config().get("prompts", {})
            if not deepseek_api_key:
                st.warning("请在侧边栏设置 DeepSeek API Key")
            else:
                with st.spinner(f"🧠 正在构建提示词上下文..."):
                    from utils.ai_advisor import build_advisor_prompt, call_deepseek_api
                    from utils.intel_manager import get_claims_for_prompt
                    from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern, get_stock_fund_flow, get_stock_fund_flow_history, get_stock_news
                    from utils.storage import load_minute_data
                    from utils.indicators import calculate_indicators
                    
                    # Logic to determine base price for Limit Calculation
                    # Default: Pre-Close (Yesterday's Close)
                    limit_base_price = pre_close
                    # If Pre-market Analysis for Tomorrow (Evening session), use Today's Close as base
                    if start_pre and datetime.datetime.now().time() > datetime.time(15, 0):
                        limit_base_price = price
                    
                    # Fetch Base Position
                    from utils.database import db_get_position
                    pos_data = db_get_position(code)
                    base_shares = pos_data.get("base_shares", 0)
                    tradable_shares = max(0, shares_held - base_shares)
                    
                    context = {
                        "base_shares": base_shares,
                        "tradable_shares": tradable_shares,
                        "limit_base_price": limit_base_price,
                        "code": code, 
                        "name": name, 
                        "price": price, 
                        "pre_close": pre_close if pre_close > 0 else price,
                        "cost": avg_cost, 
                        "current_shares": shares_held, 
                        "support": strat_res.get('support'), 
                        "resistance": strat_res.get('resistance'), 
                        "signal": signal,
                        "reason": strat_res.get('reason'), 
                        "quantity": strat_res.get('quantity'),
                        "target_position": strat_res.get('target_position', 0),
                        "stop_loss": strat_res.get('stop_loss'), 
                        "capital_allocation": current_alloc,
                        "total_capital": total_capital, 
                        "known_info": get_claims_for_prompt(code)
                    }
                    
                    minute_df = load_minute_data(code)
                    tech_indicators = calculate_indicators(minute_df)
                    tech_indicators["daily_stats"] = aggregate_minute_to_daily(minute_df, precision=get_price_precision(code))
                    
                    intraday_pattern = analyze_intraday_pattern(minute_df)
                    
                    # Merge Metaso Search + Professional News
                    metaso_claims = get_claims_for_prompt(code)
                    prof_news = get_stock_news(code, n=5)
                    full_intel_context = f"{metaso_claims}\n\n【最新权威新闻 (Professional News)】\n{prof_news}"

                    # 1. Build Prompt
                    sys_p, user_p = build_advisor_prompt(
                        context, research_context=full_intel_context, 
                        technical_indicators=tech_indicators, fund_flow_data=get_stock_fund_flow(code),
                        fund_flow_history=get_stock_fund_flow_history(code), prompt_templates=prompts,
                        intraday_summary=intraday_pattern,
                        suffix_key=target_suffix_key,
                        symbol=code
                    )
                    
                    # 2. Store in Session State for Preview
                    st.session_state[f"preview_prompt_{code}"] = {
                        "sys_p": sys_p,
                        "user_p": user_p,
                        "target_suffix_key": target_suffix_key,
                        "warning_msg": warning_msg
                    }
                    st.rerun()

        # --- Prompt Preview and Confirmation ---
        preview_key = f"preview_prompt_{code}"
        if preview_key in st.session_state:
            preview_data = st.session_state[preview_key]
            
            st.info("🔎 **提示词预览 (Prompt Preview)** - 请确认后发送")
            
            if preview_data.get("warning_msg"):
                st.warning(preview_data["warning_msg"])
            
            with st.expander("查看完整提示词内容", expanded=True):
                full_text = f"【System Prompt】\n{preview_data['sys_p']}\n\n【User Prompt】\n{preview_data['user_p']}"
                st.text_area("Request Payload", value=full_text, height=300)
                
                # Token Count Approximation
                char_count = len(full_text)
                st.caption(f"总字符数: {char_count} (约 {int(char_count/1.5)} tokens)")
            
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                if st.button("🚀 确认发送 (Send to DeepSeek)", key=f"btn_send_{code}", use_container_width=True):
                    with st.spinner("🧠 DeepSeek 正在思考 (Reasoning)... 这可能需要 30-60 秒"):
                        from utils.ai_advisor import call_deepseek_api
                        # Call API
                        content, reasoning = call_deepseek_api(
                            st.session_state.get("input_apikey", ""), 
                            preview_data['sys_p'], 
                            preview_data['user_p']
                        )
                        
                        if "Error" in content or "Request Failed" in content:
                           st.error(content)
                        else:
                            # Determine Tag
                            strategy_tag = "【盘前策略】"
                            if "intraday" in preview_data.get('target_suffix_key', ''):
                                strategy_tag = "【盘中对策】"
                                
                            # Success -> to Draft
                            st.session_state[f"pending_ai_result_{code}"] = {
                                'result': content, 
                                'reasoning': reasoning, 
                                'prompt': preview_data['user_p'],
                                'tag': strategy_tag,
                                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            # Clear Preview
                            del st.session_state[preview_key]
                            st.rerun()

            with p_col2:
                if st.button("❌ 取消 (Cancel)", key=f"btn_cancel_p_{code}", use_container_width=True):
                    del st.session_state[preview_key]
                    st.rerun()
            
            st.markdown("---")


        # --- Nested History (Inside AI Analysis) ---
        st.markdown("---")
        with st.expander("📜 历史研报记录 (Research History)", expanded=False):
            logs = load_research_log(code)
            if not logs:
                st.info("暂无历史记录")
            else:
                # 1. Prepare Data for Matching Trades
                trades = db_get_history(code)
                # Filter trades: include only explicit buy/sell, exclude allocation/override
                real_trades = [t for t in trades if t['type'] in ['buy', 'sell'] and t.get('amount', 0) > 0]
                
                # Sort logs ascending for matching interval
                sorted_logs = sorted(logs, key=lambda x: x['timestamp'])
                
                history_data = []
                log_options = {}
                
                for i, log in enumerate(sorted_logs):
                    ts = log.get('timestamp', 'N/A')
                    
                    # Determine time window
                    start_time = ts
                    end_time = sorted_logs[i+1]['timestamp'] if i < len(sorted_logs) - 1 else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Find matched trades
                    matched_tx = []
                    for t in real_trades:
                        t_ts = t['timestamp']
                        if start_time <= t_ts < end_time:
                            # Format: "Buy 100" or "Sell 500"
                            action_str = "买" if t['type'] == 'buy' else "卖"
                            matched_tx.append(f"{action_str} {int(t['amount'])}@{t['price']}")
                            
                    tx_str = "; ".join(matched_tx) if matched_tx else "-"
                    
                    # Parse simplified result
                    res_snippet = log.get('result', '')
                    # Try to extract Signal
                    s_match = re.search(r"方向:\s*(\[)?(.*?)(])?\n", res_snippet)
                    if not s_match: s_match = re.search(r"【(买入|卖出|做空|观望|持有)】", res_snippet)
                    signal_show = s_match.group(2) if s_match and len(s_match.groups()) >= 2 else (s_match.group(1) if s_match else "N/A")
                    if "N/A" in signal_show and "观望" in res_snippet[:100]: signal_show = "观望"

                    # Add to list (Insert at beginning to show latest first in table)
                    history_data.insert(0, {
                        "时间": ts,
                        "AI建议": signal_show.replace("[","").replace("]",""),
                        "实际执行": tx_str,
                        "raw_log": log
                    })
                    
                    # Prepare options for selectbox (Reverse order essentially)
                    label = f"{ts} | {signal_show} | Exec: {tx_str}"
                    log_options[label] = log

                # 2. Show Summary Table
                st.caption("策略与执行追踪")
                df_hist = pd.DataFrame(history_data)
                st.dataframe(
                    df_hist[['时间', 'AI建议', '实际执行']], 
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "实际执行": st.column_config.TextColumn("实际执行 (基于此策略)", width="large"),
                        "AI建议": st.column_config.TextColumn("AI建议", width="small"),
                    }
                )

                # 3. Detail View
                st.divider()
                selected_label = st.selectbox("查看详情 (Select Detail)", options=list(log_options.keys())[::-1], key=f"hist_sel_{code}")
                
                if selected_label:
                    selected_log = log_options[selected_label]
                    # Find corresponding row to get tx_str easily (or recompute)
                    # We can just extract from label or matched logic. 
                    # Let's re-find in history_data
                    linked_tx = "N/A"
                    for item in history_data:
                        if item["raw_log"] == selected_log:
                            linked_tx = item["实际执行"]
                            break
                            
                    s_ts = selected_log.get('timestamp', 'N/A')
                    st.markdown(f"#### 🗓️ {s_ts}")
                    
                    if linked_tx != "-":
                        st.info(f"⚡ **关联执行**: {linked_tx}")
                        
                    st.markdown(selected_log.get('result', ''))
                    
                    if selected_log.get('reasoning'):
                        with st.expander("💭 思考过程", expanded=False):
                            st.markdown(f"```text\n{selected_log['reasoning']}\n```")
                    
                    if selected_log.get('prompt'):
                        with st.expander("📝 DeepSeek 提示词", expanded=False):
                            st.markdown(f"```text\n{selected_log['prompt']}\n```")
                    if st.button("🗑️ 删除此记录", key=f"del_rsch_{code}_{s_ts}"):
                        if delete_research_log(code, s_ts):
                            st.success("已删除")
                            time.sleep(0.5)
                            st.rerun()
    
    return strat_res # Return strategy result if needed by dashboard
