import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.database import db_get_strategy_logs, db_get_watchlist, db_delete_strategy_logs_by_date
from utils.storage import load_minute_data
from utils.backtester import simulate_day, simulate_day_generator
from utils.prompt_optimizer import generate_prompt_improvement, generate_human_vs_ai_review
from utils.backtest_gen import generate_missing_strategy
from utils.config import get_settings

def render_strategy_lab():
    st.header("🧪 策略实验室 (Strategy Lab - Event Driven)")
    st.info("全天侯事件驱动回测：模拟真实的盘中决策流，验证策略有效性。")
    
    # 1. Select Stock
    watchlist = db_get_watchlist()
    selected_stock = st.selectbox("选择复盘标的", watchlist)
    
    if not selected_stock:
        return
        
    # 2. Select Date
    # Get all logs to find available dates
    all_logs = db_get_strategy_logs(selected_stock, limit=1000)
    
    # Group by Date
    log_dates = set([l['timestamp'][:10] for l in all_logs])
    
    # [v1.8.1] Get dates from Market Data as well
    minute_df = load_minute_data(selected_stock)
    data_dates = set()
    if not minute_df.empty:
        data_dates = set(minute_df['时间'].dt.strftime('%Y-%m-%d').unique())
    
    # Merge
    all_available_dates = sorted(list(log_dates | data_dates), reverse=True)
    
    if not all_available_dates:
        st.caption("暂无回测数据或策略记录。")
        return
        
    selected_date = None
    
    # Mode Selection (v1.9.0)
    mode = st.radio("模式", ["单日复盘 (Single Day)", "周期回溯 (Multi-Day)"], horizontal=True)
    
    if mode.startswith("单日"):
        selected_date = st.selectbox("选择回测日期", all_available_dates, key="single_day_date_select")
        
        if not selected_date:
            return

        # Filter logs for that day
        # ... (Rest of existing single day logic follows, we need to be careful with indentation or reuse)
        # To avoid massive indentation changes, we can use a helper or just proceed if selected_date is set.
        pass # Placeholder for logic flow, actual code stays 
    else:
        # Multi-Day Logic
        if len(all_available_dates) < 2:
            st.warning("数据不足，无法进行周期回溯")
            return
            
        min_date = datetime.strptime(all_available_dates[-1], "%Y-%m-%d") # Oldest
        max_date = datetime.strptime(all_available_dates[0], "%Y-%m-%d") # Newest
        
        # Default last 5 days
        default_start = all_available_dates[min(4, len(all_available_dates)-1)]
        default_start_date = datetime.strptime(default_start, "%Y-%m-%d")
        
        date_range = st.date_input("选择回溯周期", value=(default_start_date, max_date), min_value=min_date, max_value=max_date)
        
        if len(date_range) != 2:
            return
            
        start_date, end_date = date_range
        
        # Filter valid trading days in ascending order
        target_days = [d for d in all_available_dates if start_date.strftime("%Y-%m-%d") <= d <= end_date.strftime("%Y-%m-%d")]
        target_days.sort() # Old to New
        
        st.caption(f"回测周期: {start_date} 至 {end_date} (共 {len(target_days)} 个交易日)")
        
        if st.button("🚀 开始周期回溯 (Start Multi-Day Simulation)"):
            # Init State
            from utils.database import db_get_position_at_date, db_get_allocation, db_get_history
            import copy
            
            # Start from the state BEFORE the first day
            first_day = target_days[0]
            init_pos = db_get_position_at_date(selected_stock, first_day)
            init_cash = db_get_allocation(selected_stock)
            if init_cash <= 0: init_cash = 100000.0
            
            real_history = db_get_history(selected_stock)
            
            curr_shares = init_pos.get('shares', 0)
            curr_cost = init_pos.get('avg_cost', init_pos.get('cost', 0))
            curr_cash = init_cash
            
            # Real pipeline state carry-over
            curr_real_shares = curr_shares
            curr_real_cash = curr_cash
            
            master_curve = []
            cumulative_trades = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            from utils.backtester import simulate_day_generator
            
            base_equity = curr_cash + (curr_shares * 0) # Price unknown yet
            real_base_equity = base_equity # Approx
            
            for idx, day_str in enumerate(target_days):
                status_text.write(f"正在回测: {day_str} ({idx+1}/{len(target_days)}) ...")
                progress_bar.progress((idx) / len(target_days))
                
                # 1. Prepare Logs (and Auto-Generate if v1.8.0 active)
                # We need to act "Active Generation" here too!
                # Filter logs for this day
                t_date_obj = datetime.strptime(day_str, "%Y-%m-%d")
                d_logs = []
                for l in all_logs:
                    ts = datetime.strptime(l['timestamp'], "%Y-%m-%d %H:%M:%S")
                    is_same = (ts.date() == t_date_obj.date())
                    is_prev = ((t_date_obj.date() - ts.date()).days == 1 and ts.time().hour >= 15)
                    if is_same or is_prev: d_logs.append(l)
                
                # Active Gen Check
                if not any("盘前" in l.get('tag', '') or "盘前" in l.get('result', '') for l in d_logs):
                     with st.spinner(f"⏳ {day_str} 策略缺失，正在回补..."):
                         # Default to DeepSeek for Multi-Day simple mode
                         new_strat = generate_missing_strategy(selected_stock, "Simulated", day_str, "09:25:00", model_type="DeepSeek")
                         if new_strat: d_logs.append(new_strat)
                
                # 2. Run Sim
                # 2. Run Sim
                gen = simulate_day_generator(
                    selected_stock, day_str, d_logs, 
                    real_trades=real_history, 
                    initial_shares=curr_shares, 
                    initial_cost=curr_cost, 
                    initial_cash=curr_cash,
                    initial_real_shares=curr_real_shares,
                    initial_real_cash=curr_real_cash
                )
                
                # Consume generator (We don't need UI visualization for every tick in multi-day, just result)
                # But we do need to handle "Need Strategy" if it pops up!
                state = next(gen, None)
                day_res = None
                
                while state:
                    if state.get("type") == "need_strategy":
                        # Auto-reply for multi-day to avoid blocking? 
                        # Or just generate silently?
                        sim_time_str = state['time'].strftime("%H:%M:%S")
                        new_strat = generate_missing_strategy(selected_stock, "Simulated", day_str, sim_time_str, model_type="DeepSeek")
                        if new_strat:
                            state = gen.send(new_strat)
                        else:
                            state = next(gen, None)
                        continue
                    
                    if state.get("status") == "completed":
                        day_res = state
                        break
                    
                    state = next(gen, None)
                
                if day_res:
                    # Update States directly from Simulation Result (More Accurate)
                    curr_cash = day_res.get('final_cash', curr_cash)
                    curr_shares = day_res.get('final_shares', curr_shares)
                    
                    curr_real_cash = day_res.get('real_final_cash', curr_real_cash)
                    curr_real_shares = day_res.get('real_final_shares', curr_real_shares)
                    
                    # Accumulate Curve
                    
                    # Accumulate Curve (Daily Resolution)
                    # Only take the LAST point of the day to represent EOD Equity
                    if day_res['equity_curve']:
                        last_point = day_res['equity_curve'][-1]
                        # point: {time: HH:MM, ai_equity, ...}
                        # We use Date (YYYY-MM-DD) as x-axis
                        last_point['datetime'] = day_str # Simplified to just Date
                        master_curve.append(last_point)
                        
                    cumulative_trades.extend(day_res['trades'])
            
            progress_bar.progress(1.0)
            
            # Persist Result to Session State
            st.session_state[f"multi_sim_res_{selected_stock}"] = {
                'master_curve': master_curve,
                'init_cash': init_cash,
                'init_pos': init_pos,
                'curr_cash': curr_cash,
                'curr_shares': curr_shares,
                'curr_real_cash': curr_real_cash,
                'curr_real_shares': curr_real_shares,
                'cumulative_trades': cumulative_trades,
                'start_date': start_date,
                'end_date': end_date
            }
            st.success("周期回溯完成！")
            st.rerun()
            
        # Show Master Result (Check State)
        sim_res_key = f"multi_sim_res_{selected_stock}"
        if sim_res_key in st.session_state:
            res = st.session_state[sim_res_key]
            master_curve = res['master_curve']
            init_cash = res['init_cash']
            init_pos = res['init_pos']
            curr_cash = res['curr_cash']
            curr_shares = res['curr_shares']
            curr_real_cash = res['curr_real_cash']
            curr_real_shares = res['curr_real_shares']
            cumulative_trades = res['cumulative_trades']
            # Ensure correct scope dates
            start_date = res.get('start_date', start_date) 
            end_date = res.get('end_date', end_date)

            if master_curve:
                df = pd.DataFrame(master_curve)
                
                # Debug Data
                final_price = df.iloc[-1].get('price', 0)
                
                with st.expander("🔍 调试数据 (Debug Data)", expanded=True):
                     c1, c2, c3 = st.columns(3)
                     
                     with c1:
                         st.markdown("**初始状态 (Start)**")
                         st.write(f"资金 (Cash): ¥{init_cash:,.2f}")
                         st.write(f"持仓 (Shares): {init_pos.get('shares',0)} 股")
                         st.write(f"成本 (Avg Cost): ¥{init_pos.get('avg_cost', init_pos.get('cost', 0)):,.2f}")
                         start_equity = init_cash + (init_pos.get('shares',0) * final_price) # Estimate
                         st.write(f"总资估算: ¥{start_equity:,.2f}")

                     with c2:
                         st.markdown("**AI 最终 (AI End)**")
                         st.write(f"资金: ¥{curr_cash:,.2f}")
                         st.write(f"持仓: {curr_shares} 股")
                         ai_total = curr_cash + (curr_shares * final_price)
                         st.write(f"总资产: ¥{ai_total:,.2f}")
                         st.write(f"盈亏: ¥{ai_total - start_equity:,.2f}")
                     
                     with c3:
                         st.markdown("**实盘最终 (Real End)**")
                         st.write(f"资金: ¥{curr_real_cash:,.2f}")
                         st.write(f"持仓: {curr_real_shares} 股")
                         real_total = curr_real_cash + (curr_real_shares * final_price)
                         st.write(f"总资产: ¥{real_total:,.2f}")
                         
                     st.caption(f"结算参考价 (Latest Price): ¥{final_price}")
                
                # Plot
                st.line_chart(df.set_index('datetime')[['ai_equity', 'real_equity']])
                
                final_equity = curr_cash + (curr_shares * final_price)
                st.metric("最终 AI 权益", f"¥{final_equity:,.0f}")
                
                # v1.9.3: Multi-Day Optimization
                st.divider()
                opt_key = f"multi_opt_{selected_stock}_{start_date}_{end_date}"
                if st.button("🧠 生成全周期优化建议 (Generate Full-Cycle Optimization)", key=opt_key):
                    from utils.prompt_optimizer import generate_multi_day_review
                    from utils.config import get_settings
                    
                    with st.spinner("DeepSeek 正在分析全周期博弈数据..."):
                        settings = get_settings()
                        api_key = settings.get("deepseek_api_key")
                        if api_key:
                            # Prepare Data
                            ai_end_eq = curr_cash + (curr_shares * final_price)
                            real_end_eq = curr_real_cash + (curr_real_shares * final_price)
                            start_eq = init_cash + (init_pos.get('shares', 0) * final_price)
                            
                            ai_pnl_val = ai_end_eq - start_eq
                            real_pnl_val = real_end_eq - start_eq
                            
                            ai_pnl_pct = (ai_pnl_val / start_eq * 100) if start_eq > 0 else 0
                            real_pnl_pct = (real_pnl_val / start_eq * 100) if start_eq > 0 else 0
                            
                            # Prepare Daily Breakdown string
                            daily_breakdown = ""
                            for row in master_curve:
                                dt = row.get('datetime', '?')
                                a_eq = row.get('ai_equity', 0)
                                r_eq = row.get('real_equity', 0)
                                daily_breakdown += f"- {dt}: AI Equity {a_eq:.0f}, Real Equity {r_eq:.0f}\n"

                            summary_data = {
                                'ai_pnl': ai_pnl_pct,
                                'real_pnl': real_pnl_pct,
                                'ai_final': ai_end_eq,
                                'real_final': real_end_eq,
                                'daily_breakdown': daily_breakdown,
                                'ai_trades': cumulative_trades
                            }
                            
                            # Fetch recent logs (sampling)
                            logs_sample = [l for l in all_logs if l['timestamp'] >= start_date.strftime("%Y-%m-%d")]
                            
                            review, reasoning = generate_multi_day_review(api_key, summary_data, logs_sample)
                            st.session_state[f"multi_rev_{opt_key}"] = review
                        else:
                            st.error("请配置 DeepSeek API Key")

                if f"multi_rev_{opt_key}" in st.session_state:
                    review_text = st.session_state[f"multi_rev_{opt_key}"]
                    st.markdown("### 🧬 全周期进化建议")
                    st.info(review_text)
                    
                    # Extract Suggestion logic (Reuse existing pattern)
                    suggestion = ""
                    if "【优化建议】" in review_text:
                        parts = review_text.split("【优化建议】")
                        if len(parts) > 1:
                            suggestion = parts[1].strip(": \n")
                            
                    if suggestion:
                        st.divider()
                        st.markdown("#### 🧬 指令进化 (Evolution)")
                        from utils.config import load_config, save_prompt
                        current_conf = load_config()
                        # Align to 'deepseek_system' which is the active key
                        current_sys = current_conf.get("prompts", {}).get("deepseek_system", "")
                        
                        st.success(f"✨ 建议新增规则:\n{suggestion}")
                        new_prompt_draft = current_sys + f"\n\n[Multi-Day Opt - {end_date}]\n" + suggestion
                        
                        final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400, key=f"multi_edit_{opt_key}")
                        
                        regen_hist = st.checkbox("⚡ 应用新指令重构历史策略 (Regenerate & Re-Simulate)", value=True, key=f"regen_{opt_key}", help="勾选后，将删除当前回测周期内的旧策略记录，并使用新 Prompt 重新生成，验证优化效果。")
                        
                        if st.button("💾 更新系统指令", key=f"multi_save_{opt_key}"):
                            save_prompt("deepseek_system", final_prompt)
                            st.success("✅ 系统指令已更新！")
                            
                            if regen_hist:
                                with st.spinner("正在清除旧历史并重置回测环境..."):
                                    # 1. Identify Dates from Result
                                    # We can assume 'start_date' and 'end_date' from current context (function scope)
                                    # Iterate and delete
                                    curr = start_date
                                    from datetime import timedelta
                                    delta = end_date - start_date
                                    for i in range(delta.days + 1):
                                        d = start_date + timedelta(days=i)
                                        d_str = d.strftime("%Y-%m-%d")
                                        db_delete_strategy_logs_by_date(selected_stock, d_str)
                                    
                                    # 2. Clear Session State Result
                                    sim_res_key_del = f"multi_sim_res_{selected_stock}"
                                    if sim_res_key_del in st.session_state:
                                        del st.session_state[sim_res_key_del]
                                        
                                    st.toast("🧹 历史策略已清除，准备重新回测...")
                                    time.sleep(1)
                                    st.rerun()
                
            return # Stop here for Multi-Day

    # Single Day Logic Flow Continuation
    if mode.startswith("单日"):    
        selected_date = st.selectbox("选择回测日期", all_available_dates, key="single_day_date_select_bottom")
    
    if not selected_date:
        return

    # Filter logs for that day
    # Filter logs: Include Pre-market (from Prev Day 15:00) to Target Day Close
    # Simple heuristic: Look back 24 hours from Target Day 16:00
    target_date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
    
    day_logs = []
    for l in all_logs:
        ts = datetime.strptime(l['timestamp'], "%Y-%m-%d %H:%M:%S")
        # Check if it's within [Target 00:00, Target 23:59] OR [Prev 15:00, Target 00:00]
        # Easier: just check if it belongs to this "Trading Session"
        # Session Start: Prev Day 15:00
        # Session End: Target Day 15:30
        
        # Calculate time diff
        delta = target_date_obj - ts
        # If same day: delta.days = 0.
        # If prev day: delta.days = 1.
        
        is_same_day = (ts.date() == target_date_obj.date())
        is_prev_day_after_close = (
            (target_date_obj.date() - ts.date()).days == 1 and 
            ts.time() >= datetime.strptime("15:00", "%H:%M").time()
        )
        
        if is_same_day or is_prev_day_after_close:
            day_logs.append(l)
            
    # Active Generation Check (v1.8.0)
    has_pre_strategy = any("盘前" in l.get('tag', '') or "盘前" in l.get('result', '') for l in day_logs)
    
    if not has_pre_strategy:
        st.warning(f"⚠️ {selected_date} 缺少盘前策略记录。")
        if st.checkbox("🔄 自动回溯生成 (Active Generation)", value=True, help="消耗 Token 基于当时的历史数据生成一份盘前策略"):
             # We will handle this INSIDE the button click to avoid re-running on every render?
             # No, better to do it before Button so the log is ready for the Sim Generator.
             # Or do it lazily.
             pass
    
    day_logs.sort(key=lambda x: x['timestamp']) # Ensure sorted
    st.caption(f"该日共有 {len(day_logs)} 条策略记录 (含盘前)。")
    
    # 3. Run Simulation
    sim_key = f"sim_{selected_stock}_{selected_date}"
    btn_key = f"btn_{sim_key}"
    if st.button("⚖️ 启动人机对弈复盘 (Human vs AI Simulation)", key=btn_key):
        # 0. Initial State
        # 0. Initial State
        from utils.database import db_get_position_at_date, db_get_history
        init_pos = db_get_position_at_date(selected_stock, selected_date)
        real_history = db_get_history(selected_stock)
        
        # v1.8.0: Active Strategy Injection
        # Check again if we need to generate
        
        # [v2.0] Expert Validation Mode (Siloed Backtest)
        expert_mode = st.checkbox("🧪 专家自证模式 (Expert Validation Mode)", value=False, help="开启后，将忽略历史数据库中的记录，强制使用选定的 AI 专家实时重新生成策略。用于验证特定模型的独立作战能力。")
        candidate_expert = "DeepSeek"
        if expert_mode:
            candidate_expert = st.selectbox("⚔️ 选择考核专家 (Candidate Expert)", ["DeepSeek", "Qwen"])
            st.info(f"已进入 {candidate_expert} 独立考核模式。所有历史策略将被屏蔽，由该专家现场生成决策。")
            
            # CLEAR HISTORICAL LOGS for simulation scope (Siloed)
            day_logs = [] 
            # But we might want to keep Pre-market if it was just generated? 
            # Actually, for pure validation, we should generate Pre-market too if missing.
        
        if not any("盘前" in l.get('tag', '') or "盘前" in l.get('result', '') for l in day_logs):
             with st.spinner("⏳ 历史策略缺失，正在回溯生成 (Time Travel Generation)..."):
                 # Generate Pre-market (09:25)
                 model_for_gen = candidate_expert if expert_mode else "DeepSeek"
                 new_strat = generate_missing_strategy(selected_stock, "Simulated", selected_date, "09:25:00", model_type=model_for_gen)
                 if new_strat:
                     day_logs.append(new_strat)
                     day_logs.sort(key=lambda x: x['timestamp'])
                     st.toast(f"✅ {model_for_gen} 盘前策略已生成！")
                     time.sleep(1)
        
        # Animation UI Setup
        
        # Animation UI Setup
        st.divider()
        st.subheader(f"📊 人机对弈模拟中 ({selected_date})")
        st.caption("AI 模拟路径: 严格执行 DeepSeek 建议 | 真实路径: 重演您的实盘操作")
        
        progress_bar = st.progress(0)
        
        # Comparison Metrics
        mc1, mc2, mc3 = st.columns(3)
        ai_pnl_metric = mc1.empty()
        real_pnl_metric = mc2.empty()
        alpha_metric = mc3.empty()
        
        # Chart & Logs
        c1, c2 = st.columns([2, 1])
        with c1:
            chart_placeholder = st.empty()
        with c2:
            st.markdown("##### 📡 AI 决策流")
            log_container = st.container(height=400)
            
        # Generator
        # Generator
        from utils.database import db_get_allocation
        init_cash = db_get_allocation(selected_stock)
        if init_cash <= 0: init_cash = 100000.0 # Default if not set

        gen = simulate_day_generator(
            selected_stock, selected_date, day_logs, 
            real_trades=real_history,
            initial_shares=init_pos.get('shares', 0), 
            initial_cost=init_pos.get('avg_cost', init_pos.get('cost', 0)),
            initial_cash=init_cash
        )
        
        chart_data = []
        res = None
        base_price = None
        
        # v1.8.0: Re-implemented loop to support generator.send() for active simulation
        state = next(gen, None)
        while state:
            if state.get("type") == "need_strategy":
                with st.spinner(f"🧠 盘中策略缺失 ({state.get('point')})，正在动态研判..."):
                    # Use current simulation time from state backtest context
                    sim_time_str = state['time'].strftime("%H:%M:%S")
                    model_gen = candidate_expert if expert_mode else "DeepSeek"
                    new_strat = generate_missing_strategy(selected_stock, "Simulated", selected_date, sim_time_str, model_type=model_gen)
                    if new_strat:
                        st.toast(f"✅ 已补全 {state.get('point')} 盘中策略")
                        state = gen.send(new_strat) 
                    else:
                        state = next(gen, None)
                continue
                
            if "status" in state and state["status"] in ["completed", "no_data", "error"]:
                res = state
                break
                
            if state.get("type") in ["signal", "info", "real_trade"]:
                icon = "🤖" 
                if state["type"] == "info": icon = "ℹ️"
                if state["type"] == "real_trade": icon = "👤"
                
                log_container.write(f"{icon} {state['message']}")
                
            elif state.get("type") == "tick":
                progress_bar.progress(state["progress"])
                
                # Update Real-time Metrics
                ai_pnl = state['pnl_pct']
                real_pnl = state['real_pnl_pct']
                alpha = ai_pnl - real_pnl
                
                ai_pnl_metric.metric("AI 建议收益", f"{ai_pnl:.2f}%")
                real_pnl_metric.metric("您实盘收益", f"{real_pnl:.2f}%")
                alpha_metric.metric("AI 优化空间 (Alpha)", f"{alpha:+.2f}%", delta=alpha)
                
                # Chart Data: Comparison (All in %)
                # Capture base price at first tick for PnL calculation
                if base_price is None:
                     base_price = state['price']
                
                price_change = 0.0
                if base_price > 0:
                     price_change = (state['price'] - base_price) / base_price * 100

                row = {
                    "time": state['time'].strftime('%H:%M'), 
                    "AI 收益率 %": state['pnl_pct'],
                    "实盘收益率 %": state['real_pnl_pct'],
                    "标的涨跌幅 %": price_change
                }
                chart_data.append(row)
                
                if (len(chart_data) % 15 == 0) or state.get("trade"):
                    chart_df = pd.DataFrame(chart_data).set_index("time")
                    # Use predefined colors if possible, but default is fine.
                    chart_placeholder.line_chart(
                        chart_df[["AI 收益率 %", "实盘收益率 %", "标的涨跌幅 %"]],
                        color=["#FF4B4B", "#0068C9", "#A64D79"] # Red for AI, Blue for Real, Purple for Price
                    )
                    time.sleep(0.01)
            
            # Step to next
            state = next(gen, None)

        st.session_state[sim_key] = res
        st.rerun()

    if sim_key in st.session_state:
        res = st.session_state[sim_key]
        status = res.get('status')
        if status == 'no_data':
            st.error(f"❌ 缺少数据: {res.get('reason')}")
            return
        elif status == 'error':
            st.error(f"❌ 错误: {res.get('reason')}")
            return
            
        st.success("✅ 复盘对比完成")
        
        # Result Dashboard
        st.markdown("### 🏁 胜负结算 (Battle Result)")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("初始资产基数", f"¥{res['base_val']:,.0f}")
        r2.metric("AI 最终权益", f"¥{res['final_equity']:,.0f}", delta=f"{res['pnl_pct']:.2f}%")
        r3.metric("实盘最终权益", f"¥{res['real_final_equity']:,.0f}", delta=f"{res['real_pnl_pct']:.2f}%")
        
        alpha = res['pnl_pct'] - res['real_pnl_pct']
        r4.metric("AI 超额收益", f"{alpha:+.2f}%", delta_color="normal")
        
        # Alpha Analysis
        if alpha > 0:
            st.balloons()
            st.info(f"💡 分析显示：如果完全执行 AI 建议，您今日可多赚 ¥{ (res['final_equity'] - res['real_final_equity']):,.2f}。主要差异在于 AI 识别了成交机会。")
        elif alpha < 0:
             st.warning(f"📉 警告：您的实盘操作优于 AI 建议 ({abs(alpha):.2f}%)。")
        else:
             st.info("🤝 人机合一：您的操作与 AI 建议高度一致。")
        
        # Trades Table
        t1, t2 = st.columns(2)
        with t1:
            if res['trades']:
                st.write("🤖 AI 策略执行记录:")
                st.dataframe(pd.DataFrame(res['trades']), use_container_width=True)
            else:
                st.caption("AI 无交易")
                
        with t2:
            if res.get('real_trades_details'):
                st.write("👤 实盘操作回放:")
                # Format for display
                real_disp = []
                for rt in res['real_trades_details']:
                    real_disp.append({
                        "Time": rt['time'].strftime("%H:%M:%S"),
                        "Type": rt['type'],
                        "Price": rt['price'],
                        "Amount": rt['amount']
                    })
                st.dataframe(pd.DataFrame(real_disp), use_container_width=True)
            else:
                st.caption("实盘无交易")
            
        # Equity Curve
        if res.get('equity_curve'):
            ec_df = pd.DataFrame(res['equity_curve'])
            # We want to show % Change for consistency with dynamic chart
            if not ec_df.empty:
                # 1. Calculate Bases
                base_ai = ec_df.iloc[0]['ai_equity']
                base_real = ec_df.iloc[0]['real_equity']
                base_price = ec_df.iloc[0]['price'] if 'price' in ec_df.columns else None
                
                # 2. Compute % Change
                ec_df['AI 收益率 %'] = (ec_df['ai_equity'] - base_ai) / base_ai * 100
                ec_df['实盘收益率 %'] = (ec_df['real_equity'] - base_real) / base_real * 100
                
                cols_to_plot = ['AI 收益率 %', '实盘收益率 %']
                colors = ["#FF4B4B", "#0068C9"]
                
                if base_price and base_price > 0:
                    ec_df['标的涨跌幅 %'] = (ec_df['price'] - base_price) / base_price * 100
                    cols_to_plot.append('标的涨跌幅 %')
                    colors.append("#A64D79")
                
                st.write("📈 收益走势对比:")
                st.line_chart(ec_df.set_index('time')[cols_to_plot], color=colors)
            
        # Optimization
        pnl = res['pnl_pct']
        
        # Scenario 1: User beat AI (Alpha Analysis)
        if alpha < -0.1: # User better by at least 0.1%
            st.divider()
            st.markdown("### 🧠 人机差异诊断 (Alpha Discovery)")
            st.info("系统检测到您的操作优于 AI。这包含了宝贵的隐性知识。")
            
            battle_key = f"battle_{selected_stock}_{selected_date}"
            if st.button("🧬 提取我的 Alpha → 进化 AI (Extract Alpha)", key=battle_key):
                with st.spinner("DeepSeek 正在对比双方操作流..."):
                    settings = get_settings()
                    api_key = settings.get("deepseek_api_key")
                    if api_key:
                        # Pass real trades from result
                        real_trades = res.get('real_trades_details', [])
                        # We need logs. 'day_logs' variable is not available here after rerun.
                        # We need to fetch logs again or store them.
                        # Fetching again is safer.
                        logs_replay = db_get_strategy_logs(selected_stock, limit=100)
                        day_logs_replay = [l for l in logs_replay if l['timestamp'].startswith(selected_date)]
                        
                        review, reasoning = generate_human_vs_ai_review(api_key, res, day_logs_replay, real_trades)
                        st.session_state[f"rev_{battle_key}"] = review
                    else:
                        st.error("请配置 DeepSeek API Key")
            
            if f"rev_{battle_key}" in st.session_state:
                review_text = st.session_state[f"rev_{battle_key}"]
                st.markdown("#### 📝 诊断报告")
                st.info(review_text)
                
                # Extract Suggestion (Hardened)
                suggestion = ""
                if "【进化建议】" in review_text:
                    parts = review_text.split("【进化建议】")
                    if len(parts) > 1:
                        suggestion = parts[1].strip(": \n")
                elif "Evolution Plan" in review_text: # English fallback
                    parts = review_text.split("Evolution Plan")
                    if len(parts) > 1:
                        suggestion = parts[1].strip(": \n")
                
                if suggestion:
                    st.divider()
                    st.markdown("#### 🧬 指令进化 (Evolution)")
                    st.caption("以下是 AI 建议添加的指令。您可以编辑合并后的完整 Prompt：")
                    
                    from utils.config import load_config, save_prompt
                    current_conf = load_config()
                    # Align to deepseek_system
                    current_sys = current_conf.get("prompts", {}).get("deepseek_system", "")
                    
                    # Highlight diff
                    st.success(f"✨ 建议新增规则 (Proposed New Rule):\n{suggestion}")
                    
                    # Propose new prompt
                    new_prompt_draft = current_sys + f"\n\n[Optimization Rule - {selected_date}]\n" + suggestion
                    
                    # Edit Area
                    st.caption("全量指令预览 (您可以直接编辑下方内容):")
                    final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400)
                    
                    if st.button("💾 确认更新系统指令 (Update System Prompt)", key=f"save_bat_{battle_key}"):
                        save_prompt("deepseek_system", final_prompt)
                        st.success("✅ 系统指令已更新！")

        # Scenario 2: General Failure (only if Alpha analysis didn't run or AI also needs help)
        elif pnl < -1.0:
            st.divider()
            st.warning(f"⚠️ 亏损预警 (PnL {pnl:.2f}%)")
            opt_key = f"opt_{selected_stock}_{selected_date}"
            if st.button("🔧 启动自我修复 (Auto-Fix Strategy)", key=opt_key):
                with st.spinner("AI 正在深度反思..."):
                    settings = get_settings()
                    api_key = settings.get("deepseek_api_key")
                    if api_key:
                        # Fetch logs again
                        logs_replay = db_get_strategy_logs(selected_stock, limit=100)
                        day_logs_replay = [l for l in logs_replay if l['timestamp'].startswith(selected_date)]
                        
                        suggestion, reasoning = generate_prompt_improvement(api_key, res, day_logs_replay)
                        st.session_state[f"sug_{opt_key}"] = suggestion
                    else:
                        st.error("请配置 DeepSeek API Key")
                        
            if f"sug_{opt_key}" in st.session_state:
                sug_text = st.session_state[f"sug_{opt_key}"]
                st.markdown("### 🧠 AI 进化建议")
                st.info(sug_text)
                
                # Extract Suggestion (Hardened)
                suggestion = ""
                if "【优化建议】" in sug_text:
                    parts = sug_text.split("【优化建议】")
                    if len(parts) > 1:
                        suggestion = parts[1].strip(": \n")
                elif "Improvement" in sug_text:
                     parts = sug_text.split("Improvement")
                     if len(parts) > 1:
                        suggestion = parts[1].strip(": \n")
                        
                if suggestion:
                    st.divider()
                    st.markdown("#### 🧬 指令修复 (Fix)")
                    
                    from utils.config import load_config, save_prompt
                    current_conf = load_config()
                    # Align to deepseek_system
                    current_sys = current_conf.get("prompts", {}).get("deepseek_system", "")
                    
                    # Highlight diff
                    st.success(f"✨ 建议新增规则 (Proposed New Rule):\n{suggestion}")
                    
                    new_prompt_draft = current_sys + f"\n\n[Fix Rule - {selected_date}]\n" + suggestion
                    
                    st.caption("全量指令预览 (您可以直接编辑下方内容):")
                    final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400, key=f"area_{opt_key}")
                    
                    if st.button("💾 确认更新系统指令 (Update System Prompt)", key=f"save_opt_{opt_key}"):
                        save_prompt("deepseek_system", final_prompt)
                        st.success("✅ 系统指令已更新！")
