
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import time
from datetime import datetime
import re
from utils.strategy import analyze_volume_profile_strategy
from utils.ai_advisor import ask_deepseek_advisor
from utils.data_fetcher import aggregate_minute_to_daily, get_price_precision, analyze_intraday_pattern
from utils.indicators import calculate_indicators
from utils.config import load_config
from utils.storage import save_research_log, get_latest_strategy_log, save_daily_strategy, load_daily_strategy
from utils.monitor_logger import log_ai_heartbeat
from components.ai_monitor import render_ai_monitor

# --- Data Loading ---
@st.cache_data
def load_backtest_data_v2(code, target_date: str = None):
    """
    加载回测数据，支持动态日期选择。
    
    Args:
        code: 股票代码
        target_date: 目标回测日期 (格式: "YYYY-MM-DD")，为 None 时自动获取最新交易日
    
    Returns:
        (df_history, df_target, research_data, available_dates)
    """
    try:
        # 读取分时数据
        file_path = f"stock_data/{code}_minute.parquet"
        df = pd.read_parquet(file_path)
        # 确保 '时间' 列为 datetime 类型
        df['时间'] = pd.to_datetime(df['时间'])
        
        # 获取所有可用交易日
        available_dates = sorted(df['时间'].dt.date.unique(), reverse=True)
        
        # 动态确定目标日期
        if target_date is None and len(available_dates) > 0:
            # 默认使用最新交易日
            target_date = str(available_dates[0])
        elif target_date is None:
            target_date = ""
        
        # 分割数据：历史数据 (目标日之前) 和 目标日数据
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
            
        return df_history, df_target, research_data, [str(d) for d in available_dates]
    except Exception as e:
        # Quiet fail or return empty
        return pd.DataFrame(), pd.DataFrame(), [], []

# --- AI Parsing Helper ---
def parse_deepseek_plan(content):
    """
    Parses the AI output to find specific numerical parameters.
    Returns: dict with 'action', 'entry', 'stop_loss', 'take_profit', 'order_type', 'vol_cond'
    """
    plan = {
        "action": "观望",
        "entry": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "order_type": "低吸", # Default LIMIT
        "vol_cond": "无"      # Default NO VOL COND
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
    
    # Extract Trading Mode
    type_match = re.search(r"交易模式:\s*(\[)?(.*?)(])?(\n|$)", block_content)
    if type_match:
        mode_str = type_match.group(2).strip()
        if "追" in mode_str or "破" in mode_str: plan["order_type"] = "追涨"
    
    # Extract Volume Condition
    vol_match = re.search(r"量能条件:\s*(\[)?(.*?)(])?(\n|$)", block_content)
    if vol_match:
        vol_str = vol_match.group(2).strip()
        if "放量" in vol_str or "高" in vol_str: plan["vol_cond"] = "放量"

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
# --- Simulation Logic ---
def run_simulation(data_target, data_history, init_cash, init_shares, init_cost, prox_thresh, risk_pct, mode="ALGO", ai_plan=None, initial_reasoning="", ai_update_callback=None, code_for_log=None, progress_callback=None):

    history = []
    
    current_cash = init_cash
    current_shares = int(init_shares)
    
    # Track AI Context
    current_ai_plan = ai_plan
    current_ai_reasoning = initial_reasoning
    
    # Pre-calculate Volume Profile from HISTORY ONLY (Static View)
    vol_profile = pd.DataFrame()
    if not data_history.empty:
        hist_copy = data_history.copy()
        hist_copy['price_bin'] = hist_copy['收盘'].round(2)
        vol_profile = hist_copy.groupby('price_bin')['成交量'].sum().reset_index()

    # Pre-calculate Volume MA for Target Day (Dynamic Simulation)
    # We need a rolling window. We can pre-calc on concatenated data.
    full_data_vol = pd.concat([data_history, data_target], ignore_index=True)
    full_data_vol['vol_ma_20'] = full_data_vol['成交量'].rolling(window=20).mean()
    # Map back to target data rows
    target_start_idx = len(data_history)

    trades = []
    ai_logs = [] # Store logic updates
    
    # AI State
    ai_triggered = False
    
    total_steps = len(data_target)
    
    for i in range(total_steps):
        row = data_target.iloc[i]
        price = row['收盘']
        current_vol = row['成交量']
        
        # Get pre-calculated Vol MA (need correct index)
        global_idx = target_start_idx + i
        vol_ma_20 = full_data_vol.iloc[global_idx]['vol_ma_20']
        if pd.isna(vol_ma_20): vol_ma_20 = current_vol # Fallback

        time_str = row['时间'].strftime("%H:%M")
        
        # Report Progress
        if progress_callback and i % 5 == 0:
            plan_desc = "无策略"
            if mode == "AI" and current_ai_plan:
                p_act = current_ai_plan.get('action','观望')
                p_pr = current_ai_plan.get('entry', 0)
                p_type = current_ai_plan.get('order_type', '低吸')
                plan_desc = f"{p_act}({p_type})@{p_pr if p_pr > 0 else 'Mkt'}"
                
            progress_callback(i, total_steps, f"正在回放: {time_str} | 价位: {price} | 当前策略: {plan_desc}")
        
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
        elif mode == "AI" and current_ai_plan:
            # Current active plan
            target_action = current_ai_plan.get("action", "观望")
            entry_price = current_ai_plan.get("entry", 0.0)
            stop_price = current_ai_plan.get("stop_loss", 0.0)
            tp_price = current_ai_plan.get("take_profit", 0.0)
            
            # New Fields
            order_type = current_ai_plan.get("order_type", "低吸") # 低吸 vs 追涨
            vol_cond = current_ai_plan.get("vol_cond", "无") # 无 vs 放量

            support_level = stop_price 
            resistance_level = tp_price 
            
            # --- Unified Logic (No state locking) ---
            # AI can dictate Buy or Sell at any time.
            
            # 1. Check for Signal Trigger
            if target_action == "买入":
                should_buy = False
                buy_reason = ""
                
                # Check Entry Condition based on Order Type
                if entry_price == -1.0: # Market Buy (Always match)
                    should_buy = True
                    buy_reason = "AI策略: 现价(Market)买入"
                elif entry_price > 0:
                    if order_type == "追涨":
                        # Breakout: Price >= Target
                        check_price = price >= entry_price
                        cond_desc = f"价格突破 ({price} >= {entry_price})"
                    else:
                        # Limit (Default): Price <= Target
                        check_price = price <= entry_price
                        cond_desc = f"价格回落 ({price} <= {entry_price})"
                    
                    if check_price:
                        # Check Volume Condition if trigger price matched
                        if vol_cond == "放量":
                            if current_vol > vol_ma_20 * 1.5:
                                should_buy = True
                                buy_reason = f"AI策略: {cond_desc} 且 放量 (Vol {current_vol:.0f} > MA {vol_ma_20:.0f}*1.5)"
                            # Else: Price matched but volume didn't -> No Buy
                        else:
                            should_buy = True
                            buy_reason = f"AI策略: {cond_desc}"
                    
                if should_buy:
                    # Risk Management for Quantity
                    risk_gap = abs(entry_price - stop_price) if stop_price > 0 else (price * 0.05)
                    if risk_gap == 0: risk_gap = price * 0.01
                    
                    # Calculate qty based on Risk
                    qty = int((init_cash * risk_pct) / risk_gap)
                    qty = (qty // 100) * 100
                    
                    # Cap at available cash
                    max_afford = int(current_cash / price)
                    qty = min(qty, max_afford)
                    
                    if qty > 0:
                        action = "买入"
                        qty_delta = qty
                        reason = buy_reason

            elif target_action == "卖出":
                 should_sell = False
                 sell_reason = ""
                 
                 if current_shares > 0:
                     if entry_price == -1.0:
                         should_sell = True
                         sell_reason = "AI策略: 现价(Market)卖出"
                     elif entry_price > 0 and price >= entry_price:
                         should_sell = True
                         sell_reason = f"AI策略: 价格 {price} 触及建议价 {entry_price}"
                     
                     if should_sell:
                         qty_delta = -current_shares # Default to Close All
                         action = "卖出"
                         reason = sell_reason

            # 2. Passive Stop Loss / Take Profit (Always active if holding)
            # Only trigger if NO active Buy/Sell signal was generated above
            if action == "观望" and current_shares > 0:
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
                # current_ai_plan = None # Keep old plan until update returns
        
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
                    # current_ai_plan = None # Keep old plan until update returns
        
        # --- DYNAMIC AI UPDATE ---
        # Trigger Condition: 
        # 1. Trade Occurred (Reaction)
        # ONLY update strategy when a trade happens. Otherwise stick to the plan.
        
        should_update = trade_occurred and mode == "AI" and ai_update_callback
        
        if should_update:
            if progress_callback:
                 progress_callback(i, total_steps, f"⚡ 交易触发！AI 正在根据最新持仓重订策略...")

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
                current_holdings={"shares": current_shares, "cash": current_cash, "cost": init_cost}, # Approx cost
                previous_context={"plan": current_ai_plan, "reasoning": current_ai_reasoning}
            )
            
            if new_plan_parsed:
                current_ai_plan = new_plan_parsed
                current_ai_reasoning = new_plan_text # Simplified, using full text as reasoning context
                
                ai_logs.append({
                    "time": time_str,
                    "event": f"Strategy Update after {action}",
                    "new_plan": new_plan_parsed,
                    "thought": new_plan_text
                })
                
                # Update visual monitor heartbeat immediately
                if code_for_log:
                    log_ai_heartbeat(
                        code_for_log, 
                        new_plan_parsed.get('action', 'N/A'), 
                        f"回测动态更新 ({time_str}): {action}",
                        "Neutral" # Can extract sentiment if needed
                    )

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
    渲染回测 UI 组件。
    
    支持动态日期选择，用户可选择任意可用交易日进行回测。
    """
    # 首先获取可用日期列表
    _, _, _, available_dates = load_backtest_data_v2(code)
    
    if not available_dates:
        st.info("暂无可用回测数据。请先下载历史数据。")
        return
    
    # 日期选择器
    selected_date = st.selectbox(
        "📅 选择回测日期",
        options=available_dates,
        index=0,
        key=f"backtest_date_{code}",
        help="选择要进行回测的交易日"
    )
    
    # 加载选中日期的数据
    df_history, df_target, research_info, _ = load_backtest_data_v2(code, target_date=selected_date)
    
    if df_target.empty:
        st.warning(f"所选日期 {selected_date} 无交易数据")
        return
    
    if df_history.empty:
        st.warning(f"⚠️ 未检测到 {selected_date} 之前的历史数据。策略计算可能因缺乏数据而不准确。")

    # Expandable Settings to save space
    with st.expander("⚙️ 回测参数设置", expanded=True):
        strat_mode = st.radio("策略来源", ["基于算法 (Volume Profile)", "基于 AI (DeepSeek)"], horizontal=True, key=f"strat_source_{code}")
        
        ai_plan = None
        initial_reasoning = ""
        
        if "AI" in strat_mode:
            st.info(f"💡 这里的 AI 策略将基于 {selected_date} **开盘前** 的历史数据生成，完全排除后视镜偏差。")
            
            # --- STRATEGY PERSISTENCE LOGIC ---
            cache_key = f"ai_plan_cache_{code}_{selected_date}"
            
            # 1. Try Load from Storage (Date-Specific)
            if cache_key not in st.session_state:
                stored_plan = load_daily_strategy(code, selected_date)
                if stored_plan:
                    st.session_state[cache_key] = stored_plan
                    st.success(f"已加载 {selected_date} 的历史策略记录 ({stored_plan.get('timestamp')})")
            
            # 2. Auto-Generate if Missing (System Requirement)
            if cache_key not in st.session_state:
                 with st.spinner(f"正在为 {selected_date} 自动生成盘前策略 (首次运行)..."):
                    # Generation Logic
                    minute_hist = df_history
                    if minute_hist.empty:
                        st.error("历史数据不足，无法生成。")
                    else:
                        daily_stats = aggregate_minute_to_daily(minute_hist, precision=get_price_precision(code))
                        raw_indicators = calculate_indicators(minute_hist) 
                        last_row = df_history.iloc[-1]
                        
                        context = {
                            "code": code, "name": "模拟标的", "price": last_row['收盘'],
                            "cost": current_holding_cost if current_holding_shares > 0 else 0,
                            "current_shares": current_holding_shares,
                            "support": 0, "resistance": 0, "signal": "N/A", "reason": "Pre-market Analysis",
                            "quantity": 0, "target_position": 0, "stop_loss": 0,
                            "capital_allocation": 150000, "total_capital": 1000000, "known_info": "历史模拟模式"
                        }
                        prompts = load_config().get("prompts", {})
                        api_key = st.session_state.get("input_apikey", "")
                        
                        advice, reasoning, used_prompt = ask_deepseek_advisor(
                            api_key, context, 
                            technical_indicators=raw_indicators,
                            prompt_templates=prompts,
                            suffix_key="proposer_premarket_suffix"
                        )
                        
                        save_daily_strategy(code, selected_date, advice, reasoning, used_prompt)
                        st.session_state[cache_key] = {
                            "advice": advice, "reasoning": reasoning, "prompt": used_prompt,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state[f"ai_plan_cache_{code}"] = st.session_state[cache_key] # Update legacy pointer
                        st.success("策略自动生成并保存！")
            
            # 3. Manual Regenerate Button
            if st.button("🔄 重新生成策略 (覆盖现有)", key=f"regen_ai_plan_{code}_{selected_date}"):
                with st.spinner("正在重新生成策略..."):
                    minute_hist = df_history
                    if not minute_hist.empty:
                        daily_stats = aggregate_minute_to_daily(minute_hist, precision=get_price_precision(code))
                        raw_indicators = calculate_indicators(minute_hist) 
                        last_row = df_history.iloc[-1]
                        context = {
                            "code": code, "name": "模拟标的", "price": last_row['收盘'],
                            "cost": current_holding_cost if current_holding_shares > 0 else 0,
                            "current_shares": current_holding_shares,
                            "support": 0, "resistance": 0, "signal": "N/A", "reason": "Pre-market Analysis",
                            "quantity": 0, "target_position": 0, "stop_loss": 0,
                            "capital_allocation": 150000, "total_capital": 1000000, "known_info": "历史模拟模式"
                        }
                        prompts = load_config().get("prompts", {})
                        api_key = st.session_state.get("input_apikey", "")
                        
                        advice, reasoning, used_prompt = ask_deepseek_advisor(
                            api_key, context, 
                            technical_indicators=raw_indicators,
                            prompt_templates=prompts,
                            suffix_key="proposer_premarket_suffix"
                        )
                        
                        save_daily_strategy(code, selected_date, advice, reasoning, used_prompt)
                        st.session_state[cache_key] = {
                            "advice": advice, "reasoning": reasoning, "prompt": used_prompt,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state[f"ai_plan_cache_{code}"] = st.session_state[cache_key]
                        st.success("策略已重新生成并保存！")
            
            # Display Plan if exists
            plan_cache = st.session_state.get(cache_key)
            if plan_cache:
                with st.container(border=True):
                    st.markdown("#### 📋 盘前策略摘要")
                    ai_plan = parse_deepseek_plan(plan_cache["advice"])
                    initial_reasoning = plan_cache.get("reasoning", "")
                    
                    # 1. Key Parameters (Always Visible)
                    col_p1, col_p2, col_p3 = st.columns(3)
                    col_p1.metric("初始方向", ai_plan.get("action", "观望"))
                    col_p2.metric("建议买入价", ai_plan.get("entry", 0))
                    col_p3.metric("止损/止盈", f"{ai_plan.get('stop_loss',0)} / {ai_plan.get('take_profit',0)}")
                    
                    # 2. Detailed Content (Collapsible)
                    with st.expander("📝 查看完整分析与决策 (Detail)", expanded=False):
                        st.caption("AI 决策全文:")
                        st.text(plan_cache["advice"])
                        if plan_cache.get("reasoning"):
                            st.divider()
                            st.caption("AI 思考过程 (Reasoning):")
                            st.text(plan_cache["reasoning"])
                    
                    # 3. Prompt Content (Collapsible)
                    if plan_cache.get("prompt"):
                        with st.expander("📝 DeepSeek 提示词", expanded=False):
                            st.markdown(f"```text\n{plan_cache['prompt']}\n```")
        
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
        # Audit Interval Removed
    
    if st.button("▶️ 运行复盘 (2026-01-19)", key=f"btn_run_sim_{code}", type="primary", use_container_width=True):
        mode_key = "AI" if "AI" in strat_mode else "ALGO"
        if mode_key == "AI" and not ai_plan:
             st.error("请先生成 AI 策略计划")
             return

        # Define Callback for Dynamic AI Updates
        def ai_update_callback(current_time, current_price, trade_action, trade_qty, trade_reason, current_data_slice, current_holdings, previous_context=None):
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

                # Previous Reasoning Injection
                prev_ctx_str = ""
                if previous_context:
                    last_action = previous_context.get('plan', {}).get('action', 'N/A')
                    prev_ctx_str = f"""
                    【前序决策记忆】
                    上一轮策略: {last_action}
                    上一轮思考摘要: {previous_context.get('reasoning', '')[-500:]} (只截取最后部分)
                    """

                context = {
                    "code": code,
                    "name": "模拟标的",
                    "price": current_price,
                    "cost": c_cost,
                    "current_shares": c_shares,
                    "event_action": trade_action if trade_action != "观望" else "定期巡检",

                    "event_price": current_price,
                    "event_qty": trade_qty,
                    "event_time": current_time.strftime("%H:%M:%S"),
                    "known_info": f"触发事件: {trade_action} (数量{trade_qty})。原因: {trade_reason}。\n{guidance}\n{prev_ctx_str}" if trade_action != "观望" else f"定期巡检触发。\n{guidance}\n{prev_ctx_str}"
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
                    suffix_key="proposer_intraday_suffix" # Reuse suffix logic
                )
                
                parsed = parse_deepseek_plan(advice)
                return advice, parsed
                
            except Exception as e:
                st.error(f"AI Update Failed: {e}")
                return "", None

        # UX: Progress Bar & Status Text
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current_step, total_steps, message):
            progress = min(current_step / total_steps, 1.0)
            progress_bar.progress(progress)
            status_text.code(message) # Use code block for monospaced log look

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
            initial_reasoning=initial_reasoning,
            ai_update_callback=ai_update_callback if mode_key == "AI" else None,
            code_for_log=code,
            progress_callback=update_progress
        )
        
        # Finish Progress
        progress_bar.progress(100)
        status_text.success("回测完成！")
        time.sleep(1)
        status_text.empty()
        
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
        
        # --- AI Monitor Insertion ---
        st.markdown("---")
        render_ai_monitor(code)

