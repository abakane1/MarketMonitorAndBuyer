import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.database import db_get_strategy_logs, db_get_watchlist, db_delete_strategy_logs_by_date
from utils.storage import load_minute_data
from utils.backtester import simulate_day, simulate_day_generator
from utils.prompt_optimizer import generate_prompt_improvement, generate_human_vs_ai_review
from utils.backtest_gen import generate_missing_strategy
from utils.config import get_settings, load_config, save_prompt
from utils.backtest_utils import build_historical_context
from components.lab_strategy_panel import render_lab_strategy_panel

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
                    pass # removed local import
                    
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
                        # from utils.config import save_prompt # Global import
                        current_conf = load_config()
                        # Align to 'deepseek_system' which is the active key
                        current_sys = current_conf.get("prompts", {}).get("proposer_system", "")
                        
                        st.success(f"✨ 建议新增规则:\n{suggestion}")
                        new_prompt_draft = current_sys + f"\n\n[Multi-Day Opt - {end_date}]\n" + suggestion
                        
                        final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400, key=f"multi_edit_{opt_key}")
                        
                        regen_hist = st.checkbox("⚡ 应用新指令重构历史策略 (Regenerate & Re-Simulate)", value=True, key=f"regen_{opt_key}", help="勾选后，将删除当前回测周期内的旧策略记录，并使用新 Prompt 重新生成，验证优化效果。")
                        
                        if st.button("💾 更新系统指令", key=f"multi_save_{opt_key}"):
                            save_prompt("proposer_system", final_prompt)
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

    # Single Day Logic Flow Continuation (selected_date already assigned at top)
    if not selected_date:
        return
        
    # --- [v3.1 Lab Upgrade] Historical Strategy Generation Panel ---
    st.markdown("---")
    
    # 1. Build Context
    with st.spinner(f"正在构建 {selected_date} 的历史回测环境..."):
        # We need the code, not just name.
        # selected_stock in lab is code (from watchlist)
        ctx = build_historical_context(selected_stock, selected_date)
    
    if ctx:
        # Load Keys/Prompts
        cfg = load_config()
        prompts = cfg.get('prompts', {})
        settings = get_settings()
        api_keys = {
            'deepseek_api_key': settings.get('deepseek_api_key'),
            'qwen_api_key': settings.get('qwen_api_key')
        }
        
        # Determine Capital (Mock or Real Alloc)
        # Use DB alloc
        from utils.database import db_get_allocation
        alloc = db_get_allocation(selected_stock)
        if alloc <= 0: alloc = 100000.0
        
        # Render Panel
        render_lab_strategy_panel(ctx, api_keys, prompts, total_capital=alloc)
        
    else:
        st.error(f"无法构建 {selected_date} 的回测数据！(可能缺少当天的分钟线数据)")
        st.info("请先在仪表盘执行 'Fetch All' 或确保本地有该日期的分钟线数据。")

    st.markdown("---")

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
            ts.time() >= datetime.strptime("14:00", "%H:%M").time() # More relaxed
        )
        
        if is_same_day or is_prev_day_after_close:
            day_logs.append(l)
            
    # Active Generation Check (v1.8.0) - REMOVED/DEPRECATED by Panel
    # But we keep the warning if empty
    has_pre_strategy = any("盘前" in l.get('tag', '') or "盘前" in l.get('result', '') or "[Lab" in l.get('tag', '') for l in day_logs)
    
    if not has_pre_strategy:
        st.info(f"💡 {selected_date} 暂无策略记录。请使用上方「策略生成面板」生成一份。")
    
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
        
        # [v2.6] 3-Way Battle Mode
        st.subheader(f"⚔️ 三方博弈竞技场 (User vs AI Legion)")
        st.info("本模式将对比【实盘操作】与两支 AI 战队的表现：\n1. **DeepSeek** (红军/智库): 严谨、保守、风控导向。\n2. **Qwen** (蓝军/军团): 激进、多维度、GTO 导向。")
        
        # Expert Selection
        c1, c2 = st.columns(2)
        with c1:
            enable_deepseek = st.checkbox("启用 DeepSeek (DeepSeek-V3)", value=True)
        with c2:
            enable_qwen = st.checkbox("启用 Qwen (Qwen-Max Legion)", value=True)
            
        if not (enable_deepseek or enable_qwen):
            st.error("请至少选择一个 AI 对手")
            return

        # Time Travel Logic for BOTH models
        # We need to ensure logs exist for enabled models
        
        if st.checkbox("🔎 强制校验/补全历史策略 (Check & Backfill)", value=True):
            missing_tasks = []
            
            # Key decision points to verify
            # User Feedback: Only ensure Pre-market (09:25) is present. 
            # Intraday should be dynamic or event-driven, not forced at fixed times.
            checkpoints = ["09:25:00"]
            
            check_models = []
            if enable_deepseek: check_models.append("DeepSeek")
            if enable_qwen: check_models.append("Qwen")
            
            from datetime import timedelta, time as dtime
            
            for m in check_models:
                for cp in checkpoints:
                    # Construct time window for this checkpoint
                    cp_time = datetime.strptime(f"{selected_date} {cp}", "%Y-%m-%d %H:%M:%S")
                    
                    found = False
                    
                    # 1. Special Case: Pre-market (09:25)
                    # Any log with "盘前" or "回补" tag/content, OR time <= 09:30
                    if cp == "09:25:00":
                        found = any(
                            l.get('model', 'DeepSeek') == m and 
                            (any(k in (l.get('tag', '') + l.get('result', '')) for k in ["盘前", "回补", "Backtest"]) or datetime.strptime(l['timestamp'], "%Y-%m-%d %H:%M:%S").time() <= dtime(9, 30))
                            for l in day_logs
                        )
                    
                    if not found:
                        missing_tasks.append((m, cp))
            
            if missing_tasks:
                 # Group by time for friendlier display? No, just list.
                 # "DeepSeek @ 09:25"
                 tasks_str = ", ".join([f"{m} {t}" for m, t in missing_tasks])
                 
                 with st.spinner(f"⏳ 正在回溯生成缺失策略: {tasks_str} ..."):
                     progress_bar = st.progress(0)
                     for idx, (m, cp) in enumerate(missing_tasks):
                         new_strat = generate_missing_strategy(selected_stock, "Simulated", selected_date, cp, model_type=m)
                         if new_strat:
                             day_logs.append(new_strat)
                         progress_bar.progress((idx + 1) / len(missing_tasks))
                         
                     time.sleep(1)
                     st.rerun() # Refresh to update simulation usage
        
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

        # Parallel Simulation Loop for Selected Models
        active_models = []
        if enable_deepseek: active_models.append("DeepSeek")
        if enable_qwen: active_models.append("Qwen")

        # Initialize Generators
        generators = {}
        states = {} # Current state of each generator
        results = {} # Final results
        
        # Base Allocation
        # We need independent cash tracking for each model to be fair
        from utils.database import db_get_allocation
        base_alloc = db_get_allocation(selected_stock)
        if base_alloc <= 0: base_alloc = 100000.0
        
        for m in active_models:
             # Filter logs for this model
             # Note: Shared logs is tricky. We should filter by 'model' column.
             # Existing log structure has 'model' field (added in v2.6).
             # If 'model' is missing (legacy), assume DeepSeek.
             model_logs = [l for l in day_logs if l.get('model', 'DeepSeek') == m]
             
             # Force calculate correct cash to bypass potential stale backtester logic
             _shares = init_pos.get('shares', 0)
             _cost = init_pos.get('avg_cost', init_pos.get('cost', 0))
             # Fix Zero Cost Double Counting
             if _cost <= 0 and _shares > 0:
                 # Estimate cost from open price logic? Rare edge case here or assume 0?
                 # If we can't estimate, assume 0 means "Free Shares" -> Cash = Alloc.
                 # But sticking to audit logic:
                 _spent = 0
             else:
                 _spent = _shares * _cost
                 
             override_cash = max(0.0, base_alloc - _spent)
             
             generators[m] = simulate_day_generator(
                selected_stock, selected_date, model_logs,
                real_trades=real_history,
                initial_shares=_shares,
                initial_cost=_cost,
                initial_cash=base_alloc,
                initial_real_cash=override_cash # INJECTED FIX
             )
             states[m] = next(generators[m], None)

        chart_data = [] # Combined data for plotting
        base_price = None
        
        # Dynamic Columns Definition
        cols = [f"{m} 收益率 %" for m in active_models] + ["实盘收益率 %", "标的涨跌幅 %"]
        
        # Loop until all generators complete
        while any(s is not None for s in states.values()):
            
            # 1. Process Active States
            # We align by time? Actually simulate_day_generator yields by tick time.
            # Ideally we should synchronize, but for simplicity we iterate round-robin or just picking whoever is earliest?
            # Creating a true event loop is complex. 
            # Simplified approach: We assume ticks are roughly aligned or we just process sequentially in micro-steps.
            # Since generator yields are granular (ticks), we can just pull from all.
            
            current_row = {"time": None}
            max_progress = 0
            
            # Common Data (Price, Real PnL) - taken from any valid state
            common_price = 0
            common_real_pnl = 0
            common_time = None
            
            for m in active_models:
                st_data = states[m]
                if not st_data: continue
                
                # Handle Need Strategy
                if st_data.get("type") == "need_strategy":
                    # Auto-generate or prompt?
                    # We already did "Check & Backfill" at start.
                    # This might happen for Intraday signals generated dynamically.
                    with st.spinner(f"🧠 {m}: 盘中策略缺失 ({st_data.get('point')})..."):
                         sim_time_str = st_data['time'].strftime("%H:%M:%S")
                         new_strat = generate_missing_strategy(selected_stock, "Simulated", selected_date, sim_time_str, model_type=m)
                         if new_strat:
                             states[m] = generators[m].send(new_strat)
                         else:
                             states[m] = next(generators[m], None)
                    continue
                
                # Handle Completion
                if "status" in st_data and st_data["status"] in ["completed", "no_data", "error"]:
                    results[m] = st_data
                    states[m] = None # Stop this generator
                    continue

                # Handle Tick / Info / Trade
                if st_data.get("type") == "info":
                     log_container.write(f"ℹ️ [{m}] {st_data['message']}")
                elif st_data.get("type") == "signal":
                     log_container.write(f"🤖 [{m}] {st_data['message']}")
                elif st_data.get("type") == "real_trade":
                     # Only log once to avoid duplicates if multiple models run?
                     # Actually real_trade is yielded by all generators.
                     if m == active_models[0]: # Log only for first model
                         log_container.write(f"👤 {st_data['message']}")
                
                # Extract Time/Price if available in any message
                if st_data.get('time'):
                    common_time = st_data['time']
                if st_data.get('price'):
                    common_price = st_data['price']

                if st_data.get("type") == "tick":
                    # Capture metrics
                    current_row[f"{m} 收益率 %"] = st_data.get('pnl_pct', 0)
                    
                    # Common Data capture (last one wins)
                    common_real_pnl = st_data.get('real_pnl_pct', 0)
                    if st_data.get('progress', 0) > max_progress:
                        max_progress = st_data['progress']

                    # Advance
                    states[m] = next(generators[m], None)
                
                else:
                    # Fallback advance
                    states[m] = next(generators[m], None)

            # Update UI (Once per 'frame')
            if common_time:
                # Update Progress
                progress_bar.progress(max_progress)
                
                # Metrics Display (Use Columns)
                # We need dynamic columns based on models
                # current metrics ui is fixed mc1/mc2/mc3. Let's reuse.
                # Just show Real PnL + Top AI PnL
                
                best_ai_val = -999
                best_ai_name = ""
                for m in active_models:
                    val = current_row.get(f"{m} 收益率 %", -999)
                    if val > best_ai_val:
                        best_ai_val = val
                        best_ai_name = m
                
                # Metric 1: Best AI
                if best_ai_name:
                    ai_pnl_metric.metric(f"最佳 AI ({best_ai_name})", f"{best_ai_val:.2f}%")
                
                # Metric 2: Real
                real_pnl_metric.metric("实盘收益", f"{common_real_pnl:.2f}%")
                
                # Metric 3: Alpha (Best AI - Real)
                if best_ai_name:
                    alpha = best_ai_val - common_real_pnl
                    alpha_metric.metric("AI Alpha", f"{alpha:+.2f}%", delta=alpha)

                # Chart Data
                # Base Price Init
                if base_price is None and common_price > 0:
                    base_price = common_price
                
                # Price Change
                price_change = 0
                if base_price and base_price > 0:
                     price_change = (common_price - base_price) / base_price * 100
                
                # Row Assembly
                # Defensive check: if common_price is 0 (missing data), don't add to chart
                if common_price > 0 and common_time:
                    row_save = {
                        "time": common_time.strftime('%H:%M'),
                        "实盘收益率 %": common_real_pnl,
                        "标的涨跌幅 %": price_change
                    }
                    # Add AI columns
                    for m in active_models:
                        if f"{m} 收益率 %" in current_row:
                            row_save[f"{m} 收益率 %"] = current_row[f"{m} 收益率 %"]
                    
                    chart_data.append(row_save)
                
                # Plot
                # Plot (Refresh every 5 ticks or if at the end)
                if len(chart_data) > 0:
                    is_last_step = not any(s is not None for s in states.values())
                    if len(chart_data) % 5 == 0 or is_last_step:
                        chart_df = pd.DataFrame(chart_data)
                        if "time" in chart_df.columns:
                            chart_df = chart_df.set_index("time")
                            # Filter columns that actually exist in data
                            available_cols = [c for c in cols if c in chart_df.columns]
                            if available_cols:
                                chart_placeholder.line_chart(chart_df[available_cols])
                        
                        if not is_last_step:
                            time.sleep(0.01)

        st.session_state[sim_key] = results
        st.rerun()

    if sim_key in st.session_state:
        res = st.session_state[sim_key]
        
        # [v2.6 Fix] Detect Legacy Data (Single dict vs Multi-dict)
        # Old: {'status': 'completed', ...} -> values are strings/floats
        # New: {'DeepSeek': {...}, 'Qwen': {...}} -> values are dicts
        is_legacy = False
        if res and isinstance(res, dict):
            first_val = next(iter(res.values())) if res else None
            if first_val and not isinstance(first_val, dict):
                is_legacy = True
        
        if is_legacy:
             st.warning("⚠️ 检测到旧版缓存数据，正在清理... (Clearing Legacy Cache)")
             del st.session_state[sim_key]
             time.sleep(0.5)
             st.rerun()
        
        # Check Status (Iterate all models)
        # If any model has 'error', reported? Or as long as one valid?
        # Let's assume valid results map.
        
        
        # Check if empty
        if not res:
            st.warning("暂无回测结果")
            return
            
        st.success("✅ 复盘对比完成")
        
        # Result Dashboard
        st.markdown("### 🏁 胜负结算 (Battle Result)")
        
        # 0. Pre-market Strategy Display
        st.caption("📋 盘前策略部署 (Pre-market Strategy)")
        active_models_res = list(res.keys())
        ps_cols = st.columns(len(active_models_res))
        for idx, m in enumerate(active_models_res):
            with ps_cols[idx]:
                st.markdown(f"**🤖 {m}**")
                # Find strategy log
                # Logic: Standardize with the 'Check & Backfill' detection logic
                # Support partial match (e.g. "DeepSeek" matches "DeepSeek-V3")
                m_logs = [l for l in day_logs if m in l.get('model', 'DeepSeek')]
                
                strat_log = None
                for l in m_logs:
                    # Extract time from timestamp
                    try:
                        l_time_str = datetime.strptime(l['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
                    except:
                        l_time_str = "23:59"
                    
                    is_strat_type = (l.get('type') == 'strategy')
                    is_pre_market_time = (l_time_str <= "09:35")
                    has_pre_market_keywords = any(k in (l.get('tag', '') + l.get('result', '') + l.get('content', '')) for k in ["盘前", "回补", "Backtest"])
                    
                    if is_strat_type or is_pre_market_time or has_pre_market_keywords:
                        strat_log = l
                        break
                
                if strat_log:
                    # Extract nice time
                    s_time = strat_log.get('timestamp', '')[11:16] # HH:MM
                    with st.expander(f"📄 策略详情 ({s_time})", expanded=False):
                         # DB field is 'result', not 'content'
                         st.markdown(strat_log.get('result', '无内容'))
                         if strat_log.get('reasoning'):
                             st.info(f"🧠 AI 思考过程:\n{strat_log['reasoning']}")
                         if strat_log.get('tag'):
                             st.caption(f"标签: {strat_log['tag']}")
                else:
                    st.caption("未找到盘前策略 (No Record)")
        
        st.divider()

        # Determine Winner
        # We need to find valid results in 'res' dict.
        # res structure: {'DeepSeek': {...}, 'Qwen': {...}}
        
        cols = st.columns(len(res) + 1)
        
        # Real Performance
        real_pnl = 0
        real_final = 0
        # Get real data from ANY valid result (they share real history)
        first_valid = next(iter(res.values()))
        if first_valid:
            # v2.6.3 FIX: Override stale cash/equity from session_state with fresh calculation
            from utils.database import db_get_allocation, db_get_position_at_date
            _alloc = db_get_allocation(selected_stock) or 100000.0
            _pos = db_get_position_at_date(selected_stock, selected_date)
            _shares_start = _pos.get('shares', 0)
            _cost = _pos.get('avg_cost', 0)
            _correct_start_cash = max(0, _alloc - (_shares_start * _cost))
            
            # Get final shares from result (this is correct as it includes trades)
            real_shares = first_valid.get('real_final_shares', _shares_start)
            
            # Calculate trade cost during the day
            # Trades are: BUY = reduce cash, SELL = add cash
            # We need to adjust from start_cash to final_cash
            # For simplicity, use: final_cash = start_cash - (shares_diff * approx_price)
            shares_diff = real_shares - _shares_start
            approx_trade_cost = shares_diff * (_cost if _cost > 0 else 4.0) * 1.02 # Assume slight markup
            real_cash = _correct_start_cash - approx_trade_cost
            if real_cash < 0: real_cash = 0
            
            # Get final price from result
            final_price = first_valid.get('final_price', _cost if _cost > 0 else 4.0)
            
            # Correct final equity
            real_final = real_cash + (real_shares * final_price)
            base_val = _correct_start_cash + (_shares_start * final_price)
            real_pnl_val = real_final - base_val
            real_pnl = (real_pnl_val / base_val * 100) if base_val > 0 else 0
            
            with cols[0]:
                st.metric("👤 实盘 (User)", f"¥{real_final:,.0f}", delta=f"{real_pnl_val:+.0f} ({real_pnl:.2f}%)")
                st.caption(f"持仓: **{real_shares}** 股 | 现金: ¥{real_cash:,.0f}")
        
        # AI Performance
        idx = 1
        best_ai = None
        best_alpha = -999
        
        for model_name, r in res.items():
            if not r: continue
            
            pnl = r.get('pnl_pct', 0)
            final = r.get('final_equity', 0)
            alpha = pnl - real_pnl
            
            if alpha > best_alpha:
                best_alpha = alpha
                best_ai = model_name
                
            
            pnl_val = final - r.get('base_val', final/(1+pnl/100) if pnl != -100 else final)
            shares = r.get('final_shares', 0)
            cash = r.get('final_cash', 0)
            
            with cols[idx]:
                st.metric(f"🤖 {model_name}", f"¥{final:,.0f}", delta=f"{pnl_val:+.0f} ({pnl:.2f}%)")
                st.caption(f"持仓: **{shares}** 股 | 现金: ¥{cash:,.0f}\nAlpha: {alpha:+.2f}%")
            idx += 1
            
        st.divider()
        if best_alpha > 0:
            st.balloons()
            st.success(f"🏆 获胜者: **{best_ai}** (超额收益 {best_alpha:+.2f}%)")
        elif best_alpha < 0:
            st.warning(f"📉 警告: 实盘表现优于所有 AI 模型！")
        else:
            st.info("🤝 平局")
        
        # Alpha Analysis
        # Re-fetch for debug context (variables local to simulation block above are lost)
        from utils.database import db_get_allocation, db_get_position_at_date
        base_alloc = db_get_allocation(selected_stock) or 100000.0
        init_pos = db_get_position_at_date(selected_stock, selected_date)
        
        best_ai_res = res.get(best_ai, {})
        if best_ai_res and best_alpha > 0:
            equity_diff = best_ai_res.get('final_equity', 0) - best_ai_res.get('real_final_equity', 0)
            st.info(f"💡 分析显示：如果完全执行 **{best_ai}** 的建议，您今日可多赚 ¥{equity_diff:,.2f}。主要差异在于 AI 识别了成交机会。")
        elif best_ai_res and best_alpha < 0:
             st.warning(f"📉 警告：您的实盘操作优于 AI 建议 ({abs(best_alpha):.2f}%)。")
        else:
             st.info("🤝 人机合一：您的操作与 AI 建议高度一致。")
        

        # 1. Unified Trade Visualization
        st.write("📝 **交易行为时间轴对比 (Unified Trade Timeline)**")
        
        # Merge all trades
        all_trades_timeline = []
        
        # A. Add Real Trades (Fetch from first available result)
        # Use first_valid derived earlier (reliable)
        real_trades = first_valid.get('real_trades_details', [])
        for rt in real_trades:
            all_trades_timeline.append({
                "raw_time": rt['time'],
                "Time": rt['time'].strftime("%H:%M:%S"),
                "Type": "User (Real)",
                "Action": f"{rt['type']} {rt['amount']} @ {rt['price']}",
                "Price": rt['price'],
                "Source": "User",
                "Reason": "Manual Trade" # Default for User
            })
            
        # B. Add AI Trades
        for m_name, m_res in res.items():
            if not m_res: continue
            ai_trades = m_res.get('trades', [])
            for at in ai_trades:
                 # backtester.py returns "time" as string "HH:MM".
                 # We need to construct a full datetime for sorting.
                 dt_str = f"{selected_date} {at['time']}"
                 try:
                     # Try parsing HH:MM
                     dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                     # If parsed, seconds are 00.
                 except:     
                     dt_obj = datetime.strptime(f"{selected_date} 09:30", "%Y-%m-%d %H:%M") # Fallback
                     
                 all_trades_timeline.append({
                    "raw_time": dt_obj,
                    "Time": at['time'], # Keep original str
                    "Type": f"{m_name} (AI)",
                    "Action": f"{at['action']} {at['shares']} @ {at['price']}",
                    "Price": at['price'],
                    "Source": m_name,
                    "Reason": at.get('reason', 'Strategy Signal') # Extract Reason
                })
        
        if all_trades_timeline:
            # Sort by time
            all_trades_timeline.sort(key=lambda x: x['raw_time'])
            
            # Re-process into unified timeline (Bucket by Time point)
            timeline_map = {}
            for t in all_trades_timeline:
                # Use HH:MM key for grouping (User trades have precise seconds, round them?)
                # If User trade is 10:30:25, and AI is 10:30.
                # Let's group by HH:MM to see them together.
                tm_key = t['raw_time'].strftime("%H:%M")
                
                if tm_key not in timeline_map:
                    timeline_map[tm_key] = {
                        "Time": tm_key, 
                        "Price": t['Price'], 
                        "User": "", 
                        "DeepSeek": "", 
                        "Qwen": "",
                        "Rationale": ""  # New Column
                    }
                
                # If multiple trades in same minute, accumulate text
                src = t['Source']
                act = t['Action']
                reason = t.get('Reason', '')
                
                target_col = src
                if src not in ["User", "DeepSeek", "Qwen"]: target_col = "Other"
                
                if target_col in timeline_map[tm_key]: # Safety
                    if timeline_map[tm_key][target_col]:
                        timeline_map[tm_key][target_col] += f"; {act}"
                    else:
                        timeline_map[tm_key][target_col] = act
                
                # Accumulate Rationale
                if reason:
                     prefix = f"[{src}] " if src != "User" else ""
                     if timeline_map[tm_key]["Rationale"]:
                         timeline_map[tm_key]["Rationale"] += f"; {prefix}{reason}"
                     else:
                         timeline_map[tm_key]["Rationale"] = f"{prefix}{reason}"
            
            # Convert to DF
            sorted_times = sorted(timeline_map.keys())
            final_rows = [timeline_map[k] for k in sorted_times]
            st.dataframe(pd.DataFrame(final_rows), use_container_width=True, hide_index=True)
            
        else:
            st.caption("全天无任何交易记录")

        
        # 2. Collapsed Equity Curve
        with st.expander("📈 查看净值曲线 (Equity Curve)", expanded=False):
            st.write("多方收益走势对比 (3-Way Comparison)")
            # 1. Prepare Base DataFrame from Real History (common to all)
            if best_ai_res.get('equity_curve'):
                # Base for normalization
                full_ec_df = pd.DataFrame(best_ai_res['equity_curve'])[['time', 'real_equity', 'price']]
                base_real = full_ec_df.iloc[0]['real_equity']
                base_price = full_ec_df.iloc[0]['price']
                
                full_ec_df['您的实盘 %'] = (full_ec_df['real_equity'] - base_real) / base_real * 100
                full_ec_df['标的涨跌 %'] = (full_ec_df['price'] - base_price) / base_price * 100
                
                cols_to_plot = ['您的实盘 %', '标的涨跌 %']
                color_map = ["#0068C9", "#A64D79"] # Blue, Purple
                
                # 2. Add AI curves
                for m_name, m_res in res.items():
                    if not m_res or not m_res.get('equity_curve'): continue
                    
                    m_ec = pd.DataFrame(m_res['equity_curve'])
                    if m_ec.empty: continue
                    
                    base_ai = m_ec.iloc[0]['ai_equity']
                    m_ec[f'{m_name} 收益 %'] = (m_ec['ai_equity'] - base_ai) / base_ai * 100
                    
                    # Merge into full_ec_df
                    full_ec_df = pd.merge(full_ec_df, m_ec[['time', f'{m_name} 收益 %']], on='time', how='left')
                    cols_to_plot.append(f'{m_name} 收益 %')
                    
                    # Colors: DeepSeek (Red), Qwen (Cyan)
                    if m_name == "DeepSeek": color_map.append("#FF4B4B")
                    elif m_name == "Qwen": color_map.append("#29B09D")
                    else: color_map.append(None) # Auto
                
                # 3. Final Render
                st.line_chart(full_ec_df.set_index('time')[cols_to_plot], color=color_map)
            
        # Optimization Context
        # We need generic way to determine PnL for optimization trigger
        # Use first valid? Or check overall?
        pnl = first_valid.get('pnl_pct', 0) if first_valid else 0
        
        # Scenario 1: User beat AI (Alpha Analysis)
        if alpha < -0.1: # User better by at least 0.1%
            st.divider()
            st.markdown("### 🧠 人机差异诊断 (Alpha Discovery)")
            st.info("系统检测到您的操作优于 AI。这包含了宝贵的隐性知识。")
            
            battle_key = f"battle_{selected_stock}_{selected_date}"
            if st.button("🧬 提取我的 Alpha → 进化 AI (Extract Alpha)", key=battle_key):
                # Identify which AI model was worse?
                # Or let user pick?
                # Let's simple check: Find AI with WORST Alpha
                worst_ai = None
                worst_alpha_val = 999
                for m, r in res.items():
                    a = r.get('pnl_pct', 0) - r.get('real_pnl_pct', 0)
                    if a < worst_alpha_val:
                        worst_alpha_val = a
                        worst_ai = m
                
                target_expert = worst_ai if worst_ai else "DeepSeek"
                
                with st.spinner(f"{target_expert} 正在对比双方操作流 (Alpha Analysis)..."):
                    settings = get_settings()
                    api_keys = {
                        "deepseek_api_key": settings.get("deepseek_api_key"),
                        "qwen_api_key": settings.get("qwen_api_key") or settings.get("dashscope_api_key")
                    }
                    
                    target_key = api_keys.get("deepseek_api_key")
                    if target_expert == "Qwen": target_key = api_keys.get("qwen_api_key")

                    if target_key:
                        # Pass real trades from result
                        real_trades = first_valid.get('real_trades_details', [])
                        
                        # Fetch logs again
                        logs_replay = db_get_strategy_logs(selected_stock, limit=200)
                        # Filter for DATE and MODEL
                        day_logs_replay = [l for l in logs_replay if l['timestamp'].startswith(selected_date) and l.get('model', 'DeepSeek') == target_expert]
                        
                        review, reasoning = generate_human_vs_ai_review(target_key, res[target_expert], day_logs_replay, real_trades, model_name=target_expert)
                        st.session_state[f"rev_{battle_key}"] = review
                        st.session_state[f"target_{battle_key}"] = target_expert # Remember who we optimized
                    else:
                        st.error(f"请配置 {target_expert} API Key")
            
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
                    
                    # from utils.config import save_prompt # Global import
                    current_conf = load_config()
                    # Align to deepseek_system
                    current_sys = current_conf.get("prompts", {}).get("proposer_system", "")
                    
                    # Highlight diff
                    st.success(f"✨ 建议新增规则 (Proposed New Rule):\n{suggestion}")
                    
                    # Propose new prompt
                    new_prompt_draft = current_sys + f"\n\n[Optimization Rule - {selected_date}]\n" + suggestion
                    
                    # Edit Area
                    st.caption("全量指令预览 (您可以直接编辑下方内容):")
                    final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400)
                    
                    if st.button("💾 确认更新系统指令 (Update System Prompt)", key=f"save_bat_{battle_key}"):
                        save_prompt("proposer_system", final_prompt)
                        st.success("✅ 系统指令已更新！")

        # Scenario 2: General Failure (only if Alpha analysis didn't run or AI also needs help)
        elif pnl < -1.0:
            st.divider()
            st.warning(f"⚠️ 亏损预警 (PnL {pnl:.2f}%)")
            opt_key = f"opt_{selected_stock}_{selected_date}"
            
            # Select target for fixes
            # Default to the one with negative PnL? 
            # Or just DeepSeek?
            # Let's iterate
            failed_models = [m for m, r in res.items() if r.get('pnl_pct', 0) < -1.0]
            
            if failed_models:
                 target_fix = st.selectbox("选择需要修复的模型", failed_models, key=f"sel_fix_{opt_key}")
                 
                 if st.button(f"🔧 启动 {target_fix} 自我修复 (Auto-Fix)", key=opt_key):
                    with st.spinner(f"{target_fix} 正在深度反思..."):
                        settings = get_settings()
                        api_keys = {
                            "deepseek_api_key": settings.get("deepseek_api_key"),
                            "qwen_api_key": settings.get("qwen_api_key") or settings.get("dashscope_api_key")
                        }
                        
                        target_key = api_keys.get("deepseek_api_key")
                        if target_fix == "Qwen": target_key = api_keys.get("qwen_api_key")

                        if target_key:
                            # Fetch logs again
                            logs_replay = db_get_strategy_logs(selected_stock, limit=200)
                            day_logs_replay = [l for l in logs_replay if l['timestamp'].startswith(selected_date) and l.get('model', 'DeepSeek') == target_fix]
                            
                            suggestion, reasoning = generate_prompt_improvement(target_key, res[target_fix], day_logs_replay, model_name=target_fix)
                            st.session_state[f"sug_{opt_key}"] = suggestion
                            st.session_state[f"target_{opt_key}"] = target_fix
                        else:
                            st.error(f"请配置 {target_fix} API Key")
                        
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
                    
                    # from utils.config import save_prompt # Global import
                    current_conf = load_config()
                    # Align to deepseek_system
                    current_sys = current_conf.get("prompts", {}).get("proposer_system", "")
                    
                    # Highlight diff
                    st.success(f"✨ 建议新增规则 (Proposed New Rule):\n{suggestion}")
                    
                    new_prompt_draft = current_sys + f"\n\n[Fix Rule - {selected_date}]\n" + suggestion
                    
                    st.caption("全量指令预览 (您可以直接编辑下方内容):")
                    final_prompt = st.text_area("System Prompt Editor", value=new_prompt_draft, height=400, key=f"area_{opt_key}")
                    
                    if st.button("💾 确认更新系统指令 (Update System Prompt)", key=f"save_opt_{opt_key}"):
                        save_prompt("proposer_system", final_prompt)
                        st.success("✅ 系统指令已更新！")
