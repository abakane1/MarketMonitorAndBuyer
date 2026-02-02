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
    # find first valid price
    # find first valid price
    open_p_first = 0
    # Scan ENTIRE day for first valid price, not just 10 mins
    for i in range(len(day_df)):
        p = day_df.iloc[i]['开盘'] 
        if p > 0:
            open_p_first = p
            break
            
    if open_p_first == 0: 
        # Scan for ANY valid price field
        for col in ['收盘', '最高', '最低']:
             for i in range(len(day_df)):
                 p = day_df.iloc[i][col]
                 if p > 0:
                     open_p_first = p
                     break
             if open_p_first > 0: break
             
    if open_p_first == 0: open_p_first = initial_cost # Deep Fallback
    if open_p_first == 0: open_p_first = 1.0 # Ultimate Fallback to avoid div by zero?
    
    initial_shares_val = initial_shares * open_p_first
    
    # --- AI State ---
    # initial_cash is the "Total Allocation Limit" for this stock
    # So available cash = Allocation - Capital tied up in existing shares
    
    # 2026-01-29 Fix: If initial_cost is 0 (missing history), assume cost is current price
    # trying to avoid "Double Counting" (Full Cash + Full Stock)
    calc_cost = initial_cost
    if calc_cost <= 0 and initial_shares > 0:
        calc_cost = open_p_first
        
    spent_capital = initial_shares * calc_cost
    start_cash = max(0.0, initial_cash - spent_capital)
    
    cash = start_cash
    position = initial_shares
    
    # --- Real State ---
    # Apply same fix for Real Account
    real_spent_capital = (initial_real_shares if initial_real_shares is not None else initial_shares) * calc_cost
    if initial_real_cash is not None:
         real_start_cash = initial_real_cash
    else:
         real_start_cash = max(0.0, initial_cash - real_spent_capital)
         
    real_cash = real_start_cash
    real_position = initial_real_shares if initial_real_shares is not None else initial_shares
    
    # Base valuation at the START of the day (used for PnL %)
    # Equity = Cash + Market Value of Shares
    # v2.6.2 Fix: Simplify base valuation logic to prevent abnormal PnL percentages.
    # We use the total resources allocated/held at the VERY START of the session.
    base_val = start_cash + (initial_shares * open_p_first)
    real_base_val = real_start_cash + (real_position * open_p_first)
    
    # Defensive Floor
    if base_val <= 0: base_val = 100000.0
    if real_base_val <= 0: real_base_val = 100000.0
    
    active_buy_order = None # Limit Buy {"price": float}
    active_buy_stop = None # Stop Buy {"price": float}
    active_sell_limit = None # Limit Sell {"price": float, "qty": int}
    active_sell_stop = None # Stop Sell {"price": float}
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
        # [v2.6 Feedback] User requested REMOVAL of rigid 10:30/14:00 checkpoints.
        # Logic: First establish Pre-market (09:25), then follow market.
        # Only trigger optimization if explicit event occurs (Not forced by time).
        # decision_times = [time(10, 30), time(14, 0)] <--- DISABLED
        decision_times = [] 
        
        for dt_point in decision_times:
            if curr_time.time() >= dt_point and dt_point not in dynamic_points_triggered:
                 pass # Logic Skipped

        # A. Process Events (Logs)
        while next_log_idx < len(day_logs):
            log_entry = day_logs[next_log_idx]
            if log_entry['time'] <= curr_time:
                # Apply Signal
                sig = log_entry['signal']
                if not sig:
                    next_log_idx += 1
                    continue
                
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
                
                elif sig.action == "buy_stop":
                     # Breakout Buy
                     active_buy_stop = {"price": sig.price_target}
                     if sig.stop_loss > 0: active_sl = sig.stop_loss
                     if sig.take_profit > 0: active_tp = sig.take_profit
                     
                elif sig.action == "sell_stop":
                     # Breakdown Sell (Stop Loss or Short)
                     if position > 0:
                         active_sell_stop = {"price": sig.price_target}
                         yield {"type": "info", "message": f"设置止损单: 跌破 {sig.price_target} 卖出"}
                     else:
                         yield {"type": "info", "message": "跳过做空 (暂不支持无融券做空)"}

                    
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

        # 1.5 Check Buy Stop (Breakout)
        if active_buy_stop:
            target = active_buy_stop['price']
            if high_p >= target:
                # Triggered!
                # Triggered!
                fill_p = target
                if open_p > target and open_p > 0: fill_p = open_p # Gap up (Safe Check)
                
                if fill_p > 0 and cash > 0 and not trade_happened:
                    shares = int(cash / fill_p / 100) * 100
                    cost = shares * fill_p
                    fee = 5
                    
                    if shares > 0:
                        cash -= (cost + fee)
                        position += shares
                        avg_cost = fill_p
                        
                        trade_info = {
                            "time": curr_time.strftime("%H:%M"),
                            "action": "BUY_STOP",
                            "price": fill_p,
                            "shares": shares,
                            "reason": "突破买入"
                        }
                        trades.append(trade_info)
                        trade_happened = trade_info
                        active_buy_stop = None # One-shot
                        
                        yield {"type": "signal", "time": curr_time, "message": f"🔥 突破买入成交 @ {fill_p}"}
        
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
                
        # 3. Check Sell Stop (Breakdown / SL)
        # Combine valid SLs
        effective_sl = []
        if active_sl: effective_sl.append(active_sl)
        if active_sell_stop: effective_sl.append(active_sell_stop['price'])
        
        if effective_sl and position > 0 and not trade_happened:
            # Use HIGHEST SL triggered? Or strict logic?
            # If price drops, it hits the highest SL first.
            target = max(effective_sl)
            
            if low_p <= target:
                fill_p = target
                if open_p < target and open_p > 0: fill_p = open_p # Gap down (Safe Check)
                
                # Sell All
                trade_val = position * fill_p
                fee = max(5, trade_val * 0.001)
                tax = trade_val * 0.001
                
                real_cash = trade_val - fee - tax
                cash += real_cash
                
                trade_info = {
                    "time": curr_time.strftime("%H:%M"),
                    "action": "SELL_STOP",
                    "price": fill_p,
                    "shares": position,
                    "reason": "止损/跌破卖出"
                }
                trades.append(trade_info)
                position = 0
                trade_happened = trade_info
                active_sl = None # Reset
                active_sell_stop = None
                
                yield {"type": "signal", "time": curr_time, "message": f"🛡️ 止损卖出成交 @ {fill_p}"}
            
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
