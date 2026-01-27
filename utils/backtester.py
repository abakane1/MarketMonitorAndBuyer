import pandas as pd
from datetime import datetime, time
from utils.storage import load_minute_data
from utils.strategy_parser import StrategySignal, parse_strategy_signal

def simulate_day_generator(symbol: str, target_date_str: str, logs: list, real_trades: list = None, initial_shares: int = 0, initial_cost: float = 0.0, initial_cash: float = 100000.0, initial_real_shares: int = None, initial_real_cash: float = None):
    """
    Generator that simulates a trading day minute-by-minute with dual simulation:
    1. AI Pipeline: Strictly follows Strategy Logs
    2. Real Pipeline: Replays User's actual history from DB
    """
    # 1. Load Data
    full_df = load_minute_data(symbol)
    if real_trades is None: real_trades = []
    
    # Check data existence
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
         yield {
            "status": "error", 
            "pnl_pct": 0.0, 
            "reason": f"Invalid date format: {target_date_str}",
            "trades": [],
            "equity_curve": []
        }
         return

    has_date = not full_df.empty and any(full_df['时间'].dt.date == target_date)
    
    if not has_date:
        # Auto-sync attempt
        try:
            from utils.storage import save_minute_data
            save_minute_data(symbol)
            full_df = load_minute_data(symbol)
        except:
            pass
            
    day_df = full_df[full_df['时间'].dt.date == target_date].copy()
    if day_df.empty:
         yield {
            "status": "no_data", 
            "pnl_pct": 0.0, 
            "reason": f"No minute data for {target_date_str}",
            "trades": [],
            "equity_curve": []
        }
         return
        
    day_df = day_df.sort_values('时间').reset_index(drop=True)
    
    # 2. Setup State
    # 我们以“开盘时的总资产”作为 0% 盈亏的基数
    open_p_first = day_df.iloc[0]['开盘']
    initial_shares_val = initial_shares * open_p_first
    
    # --- AI State ---
    # initial_cash is the "Total Allocation Limit" for this stock
    # So available cash = Allocation - Capital tied up in existing shares
    spent_capital = initial_shares * initial_cost
    start_cash = max(0.0, initial_cash - spent_capital)
    
    cash = start_cash
    position = initial_shares
    
    # --- Real State ---
    real_spent_capital = (initial_real_shares if initial_real_shares is not None else initial_shares) * initial_cost
    if initial_real_cash is not None:
         real_start_cash = initial_real_cash
    else:
         real_start_cash = max(0.0, initial_cash - real_spent_capital)
         
    real_cash = real_start_cash
    real_position = initial_real_shares if initial_real_shares is not None else initial_shares
    
    # Base valuation at the START of the day (used for PnL %)
    # Equity = Cash + Market Value of Shares
    # For multi-day, base_val should ideally be the initial total equity
    base_val = start_cash + (initial_shares * open_p_first)
    real_base_val = real_start_cash + (real_position * open_p_first)
    
    if base_val <= 0: base_val = 100000.0
    if real_base_val <= 0: real_base_val = 100000.0
    
    active_buy_order = None # {"price": float}
    active_sell_limit = None # {"price": float, "qty": int}
    active_sl = None # float
    active_tp = None # float
    
    trades = [] # {"time", "action", "price", "shares", "reason"}
    equity_curve = [] # {"time", "equity", "real_equity"}
    
    # Parse real trades and sort
    # Format in DB: {'timestamp': '2026-01-23 10:26:23', 'type': 'sell', ...}
    day_real_trades = []
    for rt in real_trades:
        ts = datetime.strptime(rt['timestamp'], "%Y-%m-%d %H:%M:%S")
        if ts.date() == target_date:
            day_real_trades.append({
                "time": ts,
                "type": rt['type'].lower(),
                "price": float(rt['price']),
                "amount": int(rt['amount'])
            })
    day_real_trades.sort(key=lambda x: x['time'])
    next_real_idx = 0
    
    # Parse logs and sort
    day_logs = []
    for log in logs:
        ts = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S")
        # TRUST THE CALLER: We assume logs passed here are relevant for this session.
        # Including previous day's pre-market logs.
        day_logs.append({
            "time": ts,
            "signal": parse_strategy_signal(log),
            "original_log": log
        })
            
    day_logs.sort(key=lambda x: x['time'])
    next_log_idx = 0
    
    # Track which strategic points we've checked/requested
    dynamic_points_triggered = set()
    
    # 3. Time Loop
    total_steps = len(day_df)
    
    for idx, row in day_df.iterrows():
        curr_time = row['时间']
        open_p = row['开盘']
        high_p = row['最高']
        low_p = row['最低']
        close_p = row['收盘']
        
        # v1.8.0: Check for Dynamic Strategy Gap
        # Define key intraday decision points (e.g., 10:30, 14:00)
        decision_times = [time(10, 30), time(14, 0)]
        for dt_point in decision_times:
            if curr_time.time() >= dt_point and dt_point not in dynamic_points_triggered:
                # Check if we have any log entry specifically for this session window
                # e.g. for 10:30, check 09:30-10:30. For 14:00, check 13:00-14:00.
                window_start = (datetime.combine(target_date, dt_point) - pd.Timedelta(minutes=60)).time()
                
                has_intra_log = any(
                    l['time'].date() == target_date and 
                    l['time'].time() > window_start and
                    l['time'].time() <= curr_time.time()
                    for l in day_logs
                )
                if not has_intra_log:
                    # Signal UI to generate
                    injected = yield {
                        "type": "need_strategy",
                        "time": curr_time,
                        "point": dt_point.strftime("%H:%M")
                    }
                    if injected:
                        # User sent back a new log record
                        # Add to day_logs and re-parse
                        ts_new = datetime.strptime(injected['timestamp'], "%Y-%m-%d %H:%M:%S")
                        day_logs.append({
                            "time": ts_new,
                            "signal": parse_strategy_signal(injected),
                            "original_log": injected
                        })
                        day_logs.sort(key=lambda x: x['time'])
                    
                    dynamic_points_triggered.add(dt_point)

        # A. Process Events (Logs)
        while next_log_idx < len(day_logs):
            log_entry = day_logs[next_log_idx]
            if log_entry['time'] <= curr_time:
                # Apply Signal
                sig = log_entry['signal']
                
                # Yield Signal Event
                yield {
                    "type": "signal",
                    "time": curr_time,
                    "signal": sig,
                    "message": f"策略更新: {sig.action} @ {sig.price_target}"
                }
                
                if sig.action == "buy":
                    if position > 0:
                         yield {"type": "info", "message": f"跳过买入: 已持有 {position} 股"}
                    else:
                        active_buy_order = {"price": sig.price_target}
                    active_sl = sig.stop_loss
                    active_tp = sig.take_profit
                    
                elif sig.action == "sell":
                    if position > 0:
                        # 记录建议卖出的数量或比例
                        sell_qty = sig.quantity
                        if sell_qty <= 0:
                            # sig.position_pct 已经是小数 (如 1.0 代表 100%)
                            if sig.position_pct >= 0.99:
                                sell_qty = position
                            else:
                                sell_qty = (int(position * sig.position_pct) // 100) * 100
                        
                        if sell_qty <= 0: sell_qty = 0
                        if sell_qty > position: sell_qty = position
                            
                        active_sell_limit = {
                            "price": sig.price_target,
                            "qty": sell_qty
                        }
                        if sig.price_target == 0:
                            active_sell_limit["price"] = 0 # Market sell
                    else:
                        yield {"type": "info", "message": "跳过卖出: 当前无持仓"}
                    
                    if sig.stop_loss > 0: active_sl = sig.stop_loss
                    if sig.take_profit > 0: active_tp = sig.take_profit
                    
                next_log_idx += 1
            else:
                break
                
        # B. Execute Orders
        trade_happened = None
        
        # 1. Check Buy
        if active_buy_order:
            target = active_buy_order['price']
            if target > 0:
                if low_p <= target:
                    fill_p = target
                    if open_p < target and open_p > 0: fill_p = open_p # Gap down
                    
                    if fill_p > 0 and cash > 0:
                        shares = int(cash / fill_p / 100) * 100
                        cost = shares * fill_p
                        fee = 5 # min fee
                        
                        if shares > 0:
                            cash -= (cost + fee)
                            position += shares
                            avg_cost = fill_p # Simplified avg cost update? Ideally weighted.
                            # For simplicity we just update avg_cost to latest buy price. 
                            # v1.9.1: In future we should implement weighted average.
                        
                        trade_info = {
                            "time": curr_time.strftime("%H:%M"),
                            "action": "BUY",
                            "price": fill_p,
                            "shares": shares,
                            "reason": "信号成交"
                        }
                        trades.append(trade_info)
                        active_buy_order = None
                        trade_happened = trade_info
        
        # 2. Check Sell (Limit)
        if active_sell_limit and position > 0:
            target = active_sell_limit['price']
            should_sell = False
            fill_p = close_p
            
            if target == 0: # Market Sell
                should_sell = True
                fill_p = open_p
            elif high_p >= target:
                should_sell = True
                fill_p = target
                if open_p > target: fill_p = open_p
                
            if should_sell:
                sell_qty = active_sell_limit.get("qty", position)
                revenue = sell_qty * fill_p
                fee = max(5, revenue * 0.001)
                cash += (revenue - fee)
                
                trade_info = {
                    "time": curr_time.strftime("%H:%M"),
                    "action": "SELL",
                    "price": fill_p,
                    "shares": sell_qty,
                    "reason": "信号成交"
                }
                trades.append(trade_info)
                position -= sell_qty
                active_sell_limit = None
                trade_happened = trade_info
        
        # 3. Check SL/TP (Risk Control)
        if position > 0:
            # SL
            if active_sl and low_p <= active_sl:
                 fill_p = active_sl
                 if open_p < active_sl: fill_p = open_p
                 
                 if fill_p > 0:
                     revenue = position * fill_p
                     fee = max(5, revenue * 0.001)
                     cash += (revenue - fee)
                     
                     trade_info = {
                        "time": curr_time.strftime("%H:%M"),
                        "action": "SELL",
                        "price": fill_p,
                        "shares": position,
                        "reason": "止损触发"
                     }
                     trades.append(trade_info)
                     position = 0
                     trade_happened = trade_info
            
            # TP
            elif active_tp and high_p >= active_tp:
                 fill_p = active_tp
                 if open_p > active_tp: fill_p = open_p
                 
                 if fill_p > 0:
                     revenue = position * fill_p
                     fee = max(5, revenue * 0.001)
                     cash += (revenue - fee)
                     
                     trade_info = {
                        "time": curr_time.strftime("%H:%M"),
                        "action": "SELL",
                        "price": fill_p,
                        "shares": position,
                        "reason": "止盈触发"
                     }
                     trades.append(trade_info)
                     position = 0
                     trade_happened = trade_info

        # C. Process Real Pipeline (Replay DB records)
        while next_real_idx < len(day_real_trades):
            rt = day_real_trades[next_real_idx]
            if rt['time'] <= curr_time:
                # Execute real trade in real state
                if any(w in rt['type'] for w in ["buy", "买"]):
                    cost = rt['amount'] * rt['price']
                    real_cash -= (cost + 5)
                    real_position += rt['amount']
                    yield {"type": "real_trade", "action": "BUY", "price": rt['price'], "shares": rt['amount'], "message": f"实盘买入 {rt['amount']} 股"}
                elif any(w in rt['type'] for w in ["sell", "卖"]):
                    qty = min(rt['amount'], real_position)
                    rev = qty * rt['price']
                    real_cash += (rev - max(5, rev * 0.001))
                    real_position -= qty
                    yield {"type": "real_trade", "action": "SELL", "price": rt['price'], "shares": qty, "message": f"实盘卖出 {qty} 股"}
                elif any(w in rt['type'] for w in ["override", "修正", "reset"]):
                    target_pos = rt['amount']
                    diff = target_pos - real_position
                    real_position = target_pos
                    # Adjust cash based on diff to maintain equity continuity (Mark-to-Market)
                    # If we gained shares (diff > 0), we spent cash.
                    # If we lost shares (diff < 0), we got cash.
                    if rt['price'] > 0:
                        real_cash -= (diff * rt['price'])
                    yield {"type": "info", "message": f"实盘持仓修正: {diff:+.0f} 股"}
                next_real_idx += 1
            else:
                break

        # D. Track Equity for both
        ai_equity = cash + (position * close_p)
        real_equity = real_cash + (real_position * close_p)
        
        equity_curve.append({
            "time": curr_time.strftime("%H:%M"), 
            "ai_equity": ai_equity,
            "real_equity": real_equity,
            "price": close_p
        })
        
        # Yield Tick
        yield {
            "type": "tick",
            "progress": (idx + 1) / total_steps,
            "time": curr_time,
            "price": close_p,
            "equity": ai_equity,
            "real_equity": real_equity,
            "position": position,
            "real_position": real_position,
            "pnl_pct": (ai_equity - base_val) / base_val * 100,
            "real_position": real_position,
            "pnl_pct": (ai_equity - base_val) / base_val * 100,
            "real_pnl_pct": (real_equity - real_base_val) / real_base_val * 100,
            "trade": trade_happened
        }

    # v1.8.2: Final Post-Market Catch-up (Catch records after 15:00)
    while next_real_idx < len(day_real_trades):
        rt = day_real_trades[next_real_idx]
        # Even if market is closed, we reflect these in the final real_equity
        if any(w in rt['type'] for w in ["buy", "买"]):
            cost = rt['amount'] * rt['price']
            real_cash -= (cost + 5)
            real_position += rt['amount']
        elif any(w in rt['type'] for w in ["sell", "卖"]):
            qty = min(rt['amount'], real_position)
            rev = qty * rt['price']
            real_cash += (rev - max(5, rev * 0.001))
            real_position -= qty
        elif any(w in rt['type'] for w in ["override", "修正", "reset"]):
            real_position = rt['amount']
            # Re-calculating cash to align with final position at current price
        next_real_idx += 1

    # 4. EOD Settlement
    final_close = day_df.iloc[-1]['收盘']
    ai_end_val = cash + (position * final_close)
    real_end_val = real_cash + (real_position * final_close)
    
    result = {
        "status": "completed",
        "pnl_pct": (ai_end_val - base_val) / base_val * 100,
        "real_pnl_pct": (real_end_val - real_base_val) / real_base_val * 100,
        "final_equity": ai_end_val,
        "real_final_equity": real_end_val,
        "final_cash": cash,
        "final_shares": position,
        "real_final_cash": real_cash,
        "real_final_shares": real_position,
        "base_val": base_val,
        "trades": trades,
        "real_trades_count": len(day_real_trades),
        "real_trades_details": day_real_trades,
        "reason": "EOD Settlement",
        "equity_curve": equity_curve
    }
    yield result
    return result

def simulate_day(symbol: str, target_date_str: str, logs: list):
    """
    Wrapper for backward compatibility. 
    Consumes the generator and returns the final result.
    """
    try:
        gen = simulate_day_generator(symbol, target_date_str, logs)
        last_state = None
        for state in gen:
            last_state = state
            
        if last_state and "status" in last_state:
            return last_state
        else:
            return {
                "status": "error",
                "reason": "Simulation ended without result",
                "trades": [],
                "equity_curve": []
            }
            
    except Exception as e:
        return {
            "status": "error",
            "pnl_pct": 0.0,
            "final_equity": 100000.0,
            "trades": [],
            "reason": str(e),
            "equity_curve": []
        }
