
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import re
from utils.strategy import analyze_volume_profile_strategy
from utils.ai_advisor import ask_deepseek_advisor
from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern
from utils.indicators import calculate_indicators
from utils.config import load_config
from utils.storage import save_research_log, get_latest_strategy_log

# --- Data Loading ---
@st.cache_data
def load_backtest_data_v2(code):
    try:
        # Assuming minute data is stored as {code}_minute.parquet
        file_path = f"stock_data/{code}_minute.parquet"
        df = pd.read_parquet(file_path)
        # Ensure '时间' column is datetime
        df['时间'] = pd.to_datetime(df['时间'])
        
        # Split into History (Before 19th) and Target (19th)
        target_date = "2026-01-19"
        df_target = df[df['时间'].dt.date.astype(str) == target_date].copy().sort_values("时间").reset_index(drop=True)
        df_history = df[df['时间'].dt.date.astype(str) < target_date].copy().sort_values("时间").reset_index(drop=True)
        
        # Load Research Data for context if available
        research_path = f"stock_data/{code}_research.json"
        research_data = []
        try:
            with open(research_path, "r") as f:
                research_data = json.load(f)
        except:
            pass
            
        return df_history, df_target, research_data
    except Exception as e:
        # Quiet fail or return empty
        return pd.DataFrame(), pd.DataFrame(), []

# --- AI Parsing Helper ---
def parse_deepseek_plan(content):
    """
    Parses the AI output to find specific numerical parameters.
    Returns: dict with 'action', 'entry', 'stop_loss', 'take_profit'
    """
    plan = {
        "action": "观望",
        "entry": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0
    }
    
    # Simple RegEx extraction based on known format
    # Expecting: 【决策摘要】... 方向: 买入 ...
    
    block_match = re.search(r"【决策摘要】(.*)", content, re.DOTALL)
    if not block_match:
        # Try full text scan
        block_content = content
    else:
        block_content = block_match.group(1)
        
    s_match = re.search(r"方向:\s*(\[)?(.*?)(])?(\n|$)", block_content)
    if s_match: 
        direction = s_match.group(2).replace("[","").replace("]","").strip()
        if "买" in direction or "多" in direction or "进" in direction: plan["action"] = "买入"
        elif "卖" in direction or "空" in direction or "出" in direction: plan["action"] = "卖出"
    
    # Helper to extract first float
    def get_val(pattern):
        m = re.search(pattern, block_content)
        if m:
            val_str = m.group(1).replace("[","").replace("]","").strip()
            # If "现价" or "当前", return -1 to signal immediate
            if "现价" in val_str or "当前" in val_str:
                return -1.0
            # Find first float number
            nums = re.findall(r"(\d+\.?\d*)", val_str)
            if nums:
                return float(nums[0])
        return 0.0

    plan["entry"] = get_val(r"建议价格:\s*(.*?)(?:\n|$)")
    plan["stop_loss"] = get_val(r"止损(?:价格)?:\s*(.*?)(?:\n|$)")
    plan["take_profit"] = get_val(r"(?:止盈|目标)(?:价格)?:\s*(.*?)(?:\n|$)")
    
    return plan

# --- Simulation Logic ---
def run_simulation(data_target, data_history, init_cash, init_shares, init_cost, prox_thresh, risk_pct, mode="ALGO", ai_plan=None, ai_update_callback=None):
    history = []
    
    current_cash = init_cash
    current_shares = int(init_shares)
    
    # Pre-calculate Volume Profile from HISTORY ONLY (Static View)
    vol_profile = pd.DataFrame()
    if not data_history.empty:
        hist_copy = data_history.copy()
        hist_copy['price_bin'] = hist_copy['收盘'].round(2)
        vol_profile = hist_copy.groupby('price_bin')['成交量'].sum().reset_index()

    trades = []
    ai_logs = [] # Store logic updates
    
    # AI State
    ai_triggered = False
    
    for i in range(len(data_target)):
        row = data_target.iloc[i]
        price = row['收盘']
        time_str = row['时间'].strftime("%H:%M")
        
        signal_out = {}
        action = "观望"
        qty_delta = 0
        reason = ""
        support_level = 0.0
        resistance_level = 0.0
        
        # ALGO MODE
        if mode == "ALGO":
            signal_out = analyze_volume_profile_strategy(
                current_price=price,
                vol_profile=vol_profile,
                total_capital=init_cash, 
                risk_per_trade=risk_pct,
                current_shares=current_shares,
                proximity_threshold=prox_thresh
            )
            action = signal_out['signal']
            qty_delta = signal_out['quantity']
            reason = signal_out['reason']
            support_level = signal_out['support']
            resistance_level = signal_out['resistance']
            
        # AI MODE
        elif mode == "AI" and ai_plan:
            # Current active plan
            target_action = ai_plan.get("action", "观望")
            entry_price = ai_plan.get("entry", 0.0)
            stop_price = ai_plan.get("stop_loss", 0.0)
            tp_price = ai_plan.get("take_profit", 0.0)
            
            support_level = stop_price 
            resistance_level = tp_price 
            
            # 1. Entry Logic
            if not ai_triggered: # Not in a trade initiated by THIS cycle's plan
                if target_action == "买入":
                    should_buy = False
                    buy_reason = ""
                    
                    if entry_price == -1.0:
                        should_buy = True
                        buy_reason = "AI策略: 现价(Market)买入"
                    elif entry_price > 0 and price <= entry_price:
                        should_buy = True
                        buy_reason = f"AI策略: 价格 {price} 优于或等于建议价 {entry_price}"
                        
                    if should_buy:
                        risk_gap = abs(entry_price - stop_price) if stop_price > 0 else (price * 0.05)
                        if risk_gap == 0: risk_gap = price * 0.01 # Fallback
                        qty = int((init_cash * risk_pct) / risk_gap)
                        qty = (qty // 100) * 100
                        max_afford = int(current_cash / price)
                        qty = min(qty, max_afford)
                        
                        if qty > 0:
                            action = "买入"
                            qty_delta = qty
                            reason = buy_reason
                            # Note: ai_triggered will be handled effectively by the state update below 
                            # because we will re-ask AI for a new plan (Manage Position)

                elif target_action == "卖出":
                     should_sell = False
                     sell_reason = ""
                     
                     if entry_price == -1.0:
                         should_sell = True
                         sell_reason = "AI策略: 现价(Market)卖出"
                     elif entry_price > 0 and price >= entry_price:
                         should_sell = True
                         sell_reason = f"AI策略: 价格 {price} 优于或等于建议价 {entry_price}"
                     
                     if should_sell:
                         qty_delta = -current_shares # Exit all custom logic could be better
                         if qty_delta != 0:
                            action = "卖出"
                            reason = sell_reason

            else:
                # 2. Exit Logic (Manage Position) - Only if we don't update plan immediately
                # But with dynamic update, if we are holding, the AI Plan should BE "Hold" or "Sell at X".
                # So we just follow the current plan's Stop/TP.
                
                if current_shares > 0: 
                     if stop_price > 0 and price <= stop_price:
                         action = "卖出"
                         qty_delta = -current_shares
                         reason = f"AI执行: 止损触发 ({price} <= {stop_price})"
                     elif tp_price > 0 and price >= tp_price:
                         action = "卖出"
                         qty_delta = -current_shares
                         reason = f"AI执行: 止盈触发 ({price} >= {tp_price})"

        # Execute Trade
        execution_price = price 
        trade_occurred = False
        
        if action == "买入" and qty_delta > 0:
            cost = qty_delta * execution_price
            if current_cash >= cost:
                current_cash -= cost
                current_shares += qty_delta
                trades.append({
                    "time": time_str,
                    "action": "BUY",
                    "price": execution_price,
                    "qty": qty_delta,
                    "reason": reason
                })
                trade_occurred = True
                ai_triggered = True # We are now in a position (or added to one)
        
        elif action == "卖出" or (action == "观望" and qty_delta < 0): 
            if qty_delta < 0:
                sell_qty = abs(qty_delta)
                if current_shares >= sell_qty:
                    revenue = sell_qty * execution_price
                    current_cash += revenue
                    current_shares -= sell_qty
                    trades.append({
                        "time": time_str,
                        "action": "SELL",
                        "price": execution_price,
                        "qty": sell_qty,
                        "reason": reason
                    })
                    trade_occurred = True
                    if current_shares == 0:
                        ai_triggered = False # Reset trigger state
        
        # --- DYNAMIC AI UPDATE ---
        if trade_occurred and mode == "AI" and ai_update_callback:
            # Pause and ask AI for new directions
            # current_data_slice should be the minute data up to the current point (inclusive)
            current_data_slice = pd.concat([data_history, data_target.iloc[:i+1]])
            
            new_plan_text, new_plan_parsed = ai_update_callback(
                current_time=row['时间'],
                current_price=price,
                trade_action=action,
                trade_qty=abs(qty_delta),
                trade_reason=reason,
                current_data_slice=current_data_slice,
                current_holdings={"shares": current_shares, "cash": current_cash, "cost": init_cost} # Approx cost
            )
            
            if new_plan_parsed:
                ai_plan = new_plan_parsed
                ai_logs.append({
                    "time": time_str,
                    "event": f"Strategy Update after {action}",
                    "new_plan": new_plan_parsed,
                    "thought": new_plan_text
                })
                # If we just bought, the new plan likely sets SL/TP for holding.
                # If we just sold, the new plan might be "Wait" or "Buy lower".

        # Record State
        history.append({
            "time": row['时间'],
            "price": price,
            "cash": current_cash,
            "shares": current_shares,
            "equity": current_cash + (current_shares * price),
            "signal": action,
            "support": support_level,
            "resistance": resistance_level
        })
        
    return pd.DataFrame(history), trades, ai_logs

# --- Main Render Function ---
def render_backtest_widget(code, current_holding_shares=0, current_holding_cost=0.0):
    """
    Renders the Backtest UI for a specific stock code inside the parent container.
    """
    df_history, df_target, research_info = load_backtest_data_v2(code)
    
    if df_target.empty:
        st.info("暂无回测数据 (仅支持 2026-01-19)")
        return
    
    if df_history.empty:
        st.warning("⚠️ 未检测到 19 号以前的历史数据。策略确定可能因缺乏数据而不准确。")

    # Expandable Settings to save space
    with st.expander("⚙️ 回测参数设置", expanded=True):
        strat_mode = st.radio("策略来源", ["基于算法 (Volume Profile)", "基于 AI (DeepSeek)"], horizontal=True, key=f"strat_source_{code}")
        
        ai_plan = None
        
        if "AI" in strat_mode:
            st.info("💡 这里的 AI 策略将基于 19 号 **开盘前** 的历史数据生成，完全排除后视镜偏差。")
            
            # Auto-load latest strategy if not in session
            cache_key = f"ai_plan_cache_{code}"
            if cache_key not in st.session_state:
                latest_log = get_latest_strategy_log(code)
                if latest_log:
                    st.session_state[cache_key] = {
                        "advice": latest_log.get("result", ""),
                        "reasoning": latest_log.get("reasoning", ""),
                        "source": f"本地历史记录 ({latest_log.get('timestamp')})"
                    }
                    st.info(f"策略已从本地历史记录加载 ({latest_log.get('timestamp')})")
            
            # Button to Generate Pre-Market Plan
            if st.button("🧠 生成盘前交易计划 (DeepSeek)", key=f"gen_ai_plan_{code}"):
                with st.spinner("正在回溯历史并生成策略..."):
                    # 1. Prepare Historical Context
                    minute_hist = df_history
                    if minute_hist.empty:
                        st.error("历史数据不足，无法生成。")
                    else:
                        daily_stats = aggregate_minute_to_daily(minute_hist, precision=get_price_precision(code))
                        raw_indicators = calculate_indicators(minute_hist) # Last point of history
                        
                        # Mock context
                        # We pretend we are at the END of df_history
                        last_row = df_history.iloc[-1]
                        
                        context = {
                            "code": code,
                            "name": "模拟标的", # Can fetch name if needed
                            "price": last_row['收盘'],
                            "cost": current_holding_cost if current_holding_shares > 0 else 0, # Use Real Cost if available
                            "current_shares": current_holding_shares,
                            "support": 0, # Let AI determine
                            "resistance": 0,
                            "signal": "N/A",
                            "reason": "Pre-market Analysis",
                            "quantity": 0,
                            "target_position": 0,
                            "stop_loss": 0,
                            "capital_allocation": 150000,
                            "total_capital": 1000000,
                            "known_info": "历史模拟模式"
                        }
                        
                        prompts = load_config().get("prompts", {})
                        api_key = st.session_state.get("input_apikey", "")
                        
                        advice, reasoning, _ = ask_deepseek_advisor(
                            api_key, context, 
                            technical_indicators=raw_indicators,
                            # Ideally pass history fund flow too
                            prompt_templates=prompts,
                            suffix_key="deepseek_new_strategy_suffix" # Force independent strategy
                        )
                        
                        # Save execution plan to session state
                        st.session_state[f"ai_plan_cache_{code}"] = {
                            "advice": advice,
                            "reasoning": reasoning
                        }
                        st.success("策略已生成！")
            
            # Display Plan if exists
            plan_cache = st.session_state.get(f"ai_plan_cache_{code}")
            if plan_cache:
                with st.container(border=True):
                    st.markdown("#### 📋 盘前策略摘要")
                    st.text(plan_cache["advice"])
                    ai_plan = parse_deepseek_plan(plan_cache["advice"])
                    st.write("解析参数:", ai_plan)
        
        # Dynamic Defaults
        default_price = 0.0
        if not df_target.empty:
            default_price = float(df_target.iloc[0]['开盘'])
            
        # If user has real positions, prioritize them
        def_shares = int(current_holding_shares) if current_holding_shares > 0 else 0
        def_cost = float(current_holding_cost) if current_holding_shares > 0 else default_price
            
        c1, c2, c3 = st.columns(3)
        initial_cash = c1.number_input("初始资金", value=150000.0, step=1000.0, key=f"sim_cash_{code}")
        # Default shares to real holding or 0
        initial_shares = c2.number_input("初始持仓", value=def_shares, step=100, key=f"sim_shares_{code}")
        # Default cost to real cost or open price
        initial_cost = c3.number_input("持仓成本", value=def_cost, step=0.01, format="%.2f", key=f"sim_cost_{code}")
        
        c4, c5 = st.columns(2)
        prox_thresh_pct = c4.slider("信号阈值 (%)", 0.5, 5.0, 3.0, 0.1, key=f"sim_prox_{code}") / 100.0
        risk_pct = c5.slider("风控比例 (%)", 0.5, 5.0, 2.0, 0.1, key=f"sim_risk_{code}") / 100.0
    
    if st.button("▶️ 运行复盘 (2026-01-19)", key=f"btn_run_sim_{code}", type="primary", use_container_width=True):
        mode_key = "AI" if "AI" in strat_mode else "ALGO"
        if mode_key == "AI" and not ai_plan:
             st.error("请先生成 AI 策略计划")
             return

        # Define Callback for Dynamic AI Updates
        def ai_update_callback(current_time, current_price, trade_action, trade_qty, trade_reason, current_data_slice, current_holdings):
            # 1. Build Intraday Context
            # We need to process the slice to get indicators
            try:
                # Ensure slice is valid
                if current_data_slice.empty: return "", None
                
                # We need to pass data to helper functions. 
                # Note: They usually expect a full DF, so slice is fine.
                minute_resampled = current_data_slice.copy()
                
                intraday_summary = analyze_intraday_pattern(minute_resampled)
                tech_inds = calculate_indicators(minute_resampled)
                
                # 2. Construct Prompt Context
                c_shares = current_holdings.get('shares', 0)
                c_cost = current_holdings.get('cost', 0)
                
                # Contextual Guidance based on State
                guidance = ""
                if c_shares == 0:
                    guidance = "当前状态: [已空仓]。核心任务: 寻找下一次获利【进场机会】(低吸/接回) 或 保持观望。⚠️ 注意: 当前无持仓，请勿建议卖出。"
                else:
                    guidance = f"当前状态: [持仓 {c_shares}股, 成本 {c_cost:.2f}]。核心任务: 监控持仓风险，更新【止损/止盈位】或 寻找【高抛/加仓】机会。"

                context = {
                    "code": code,
                    "name": "模拟标的",
                    "price": current_price,
                    "cost": c_cost,
                    "current_shares": c_shares,
                    "event_action": trade_action,
                    "event_price": current_price,
                    "event_qty": trade_qty,
                    "event_time": current_time.strftime("%H:%M:%S"),
                    "known_info": f"刚刚触发交易: {trade_action} (数量{trade_qty})。原因: {trade_reason}。\n{guidance}"
                }
                
                # 3. Call AI
                prompts = load_config().get("prompts", {})
                api_key = st.session_state.get("input_apikey", "")
                
                # We need a specific prompt template for "Update Strategy"
                # If not exists, use a generic one or append to base.
                # Here we use 'deepseek_base' but inject the Event Info into 'known_info'.
                
                advice, reasoning, _ = ask_deepseek_advisor(
                    api_key, context, 
                    technical_indicators=tech_inds,
                    intraday_summary=intraday_summary,
                    prompt_templates=prompts,
                    suffix_key="deepseek_new_strategy_suffix" # Reuse suffix logic
                )
                
                parsed = parse_deepseek_plan(advice)
                return advice, parsed
                
            except Exception as e:
                st.error(f"AI Update Failed: {e}")
                return "", None

        with st.spinner("正在逐分钟推演 (AI 动态盯盘中)..."):
            res_df, trade_log, ai_activity_logs = run_simulation(
                df_target, 
                df_history,
                initial_cash, 
                initial_shares, 
                initial_cost, 
                prox_thresh_pct,
                risk_pct,
                mode=mode_key,
                ai_plan=ai_plan,
                ai_update_callback=ai_update_callback if mode_key == "AI" else None
            )
        
        # Metrics
        final_equity = res_df.iloc[-1]['equity']
        start_equity = initial_cash + (initial_shares * df_target.iloc[0]['开盘'])
        pnl = final_equity - start_equity
        pnl_pct = (pnl / start_equity) * 100 if start_equity > 0 else 0
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("最终权益", f"{final_equity:,.0f}", f"{pnl:+.0f}")
        m_col2.metric("盈亏比", f"{pnl_pct:+.2f}%")
        m_col3.metric("交易次数", len(trade_log))
        
        # Charts (Compact)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=res_df['time'], y=res_df['price'], mode='lines', name='股价',
            line=dict(color='gray', width=1)
        ))
        
        # Add Lines for AI levels if AI mode
        if mode_key == "AI" and ai_plan:
             ent = ai_plan.get("entry", 0)
             tp = ai_plan.get("take_profit", 0)
             sl = ai_plan.get("stop_loss", 0)
             if ent > 0: fig.add_hline(y=ent, line_dash="dash", line_color="blue", annotation_text="AI买入")
             if tp > 0: fig.add_hline(y=tp, line_dash="dash", line_color="green", annotation_text="AI止盈")
             if sl > 0: fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="AI止损")

        # Markers
        buys = [t for t in trade_log if t['action'] == 'BUY']
        sells = [t for t in trade_log if t['action'] == 'SELL']
        
        if buys:
            fig.add_trace(go.Scatter(
                x=[pd.to_datetime("2026-01-19 " + t['time']) for t in buys],
                y=[t['price'] for t in buys],
                mode='markers', name='买入',
                marker=dict(symbol='triangle-up', size=10, color='red')
            ))
        if sells:
            fig.add_trace(go.Scatter(
                x=[pd.to_datetime("2026-01-19 " + t['time']) for t in sells],
                y=[t['price'] for t in sells],
                mode='markers', name='卖出',
                marker=dict(symbol='triangle-down', size=10, color='green')
            ))
            
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            xaxis_title=None,
            yaxis_title="价格",
            showlegend=True,
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor='center')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Trade Log
        if trade_log:
            st.caption("📝 交易明细")
            st.dataframe(pd.DataFrame(trade_log), hide_index=True)
            
        # AI Activity Log
        if mode_key == "AI" and ai_activity_logs:
            with st.expander("🤖 AI 动态盯盘日志 (Chain of Thought)", expanded=True):
                for log in ai_activity_logs:
                    st.markdown(f"**[{log['time']}] {log['event']}**")
                    st.caption("AI 思考:")
                    st.text(log['thought'])
                    st.caption(f"新策略: {log['new_plan']}")
                    st.divider()
        else:
            if not trade_log:
                st.caption("当日无交易")
