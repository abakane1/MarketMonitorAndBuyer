import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class StrategySignal:
    timestamp: str
    action: str = "hold"  # buy, sell, hold
    price_target: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    quantity: int = 0
    position_pct: float = 1.0 # 0.0 to 1.0
    confidence: str = ""
    raw_content: str = ""

def parse_price(text: str) -> float:
    # Extract first float
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        return float(match.group(1))
    return 0.0

def parse_strategy_signal(log_entry: dict) -> StrategySignal:
    """
    Parses a DB log entry into a structured signal.
    """
    content = log_entry.get("result", "")
    timestamp = log_entry.get("timestamp", "")
    
    signal = StrategySignal(timestamp=timestamp, raw_content=content)
    
    # Mode 1: Structured Block (Intraday usually)
    # 【决策摘要】 或 【盘中对策】 或 【盘前策略】
    if any(tag in content for tag in ["【决策摘要】", "【盘中对策】", "【盘前策略】"]):
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("方向:"):
                val = line.split(":", 1)[1].strip()
                if "买" in val: signal.action = "buy"
                elif "卖" in val: signal.action = "sell"
                else: signal.action = "hold"
            
            elif line.startswith("建议价格:") or line.startswith("挂单价格:"):
                signal.price_target = parse_price(line)
            
            elif line.startswith("建议仓位:") or line.startswith("卖出仓位:"):
                val = line.split(":", 1)[1].strip()
                if "%" in val:
                    pct_match = re.search(r"(\d+)", val)
                    if pct_match:
                        signal.position_pct = float(pct_match.group(1)) / 100.0
                elif "股" in val:
                    qty_match = re.search(r"(\d+)", val)
                    if qty_match:
                        signal.quantity = int(qty_match.group(1))
            
            elif line.startswith("止损价格:") or line.startswith("止损位:"):
                signal.stop_loss = parse_price(line)
                
            elif line.startswith("止盈价格:") or line.startswith("止盈位:"):
                signal.take_profit = parse_price(line)
                
        return signal

    # Mode 3: Conditional / Markdown List (DeepSeek/Qwen V3)
    # Pattern: "- **突破阻力位4.25**:"
    # Pattern: "- **跌破支撑位3.83**:"
    
    # Check for Breakout (Buy Stop)
    breakout_match = re.search(r"突破.*?(\d+\.\d{2})", content)
    if breakout_match:
        signal.price_target = float(breakout_match.group(1))
        signal.action = "buy_stop" # New Action Type
        
        # Look for details under this section
        # Heuristic: If we found a breakout price, we assume it's the primary actionable advice unless contradicted.
        # Check for dependent take profit/stop loss nearby
        sub_text = content[breakout_match.end():] # Look ahead
        sl_match = re.search(r"止损.*?(\d+\.\d{2})", sub_text)
        if sl_match: signal.stop_loss = float(sl_match.group(1))
        
        return signal

    # Check for Breakdown (Sell Stop / Short)
    breakdown_match = re.search(r"跌破.*?(\d+\.\d{2})", content)
    if breakdown_match:
        signal.price_target = float(breakdown_match.group(1))
        # If we have shares, this is a Stop Loss (Sell Stop)
        # If we don't, it might be Short.
        # Safe default: sell_stop
        signal.action = "sell_stop"
        
        return signal

    # Keyword Heuristics (Fallback)
    # Buy: "低吸", "买入", "做多"
    # Sell: "止盈", "卖出", "清仓"
    
    # Simplified Logic: Identify PRIMARY intent
    # Look for "Plan A" line
    plan_a_match = re.search(r"Plan A.*[:：](.*)", content)
    if plan_a_match:
        plan_text = plan_a_match.group(1)
        
        # Determine Trigger Price
        # "在 3.85 附近... " -> 3.85
        prices = re.findall(r"(\d+\.\d{2})", plan_text)
        if prices:
            signal.price_target = float(prices[0])
            
        # Determine Action
        if any(w in plan_text for w in ["买", "吸", "接", "做多"]):
            signal.action = "buy"
        elif any(w in plan_text for w in ["卖", "出", "减", "清"]):
            signal.action = "sell"
            
        # Try finding Stop Loss in subsequent text
        sl_match = re.search(r"(?:止损|防守).*?(\d+\.\d{2})", content)
        if sl_match:
            signal.stop_loss = float(sl_match.group(1))
            
        # TP
        tp_match = re.search(r"(?:止盈|目标).*?(\d+\.\d{2})", content)
        if tp_match:
            signal.take_profit = float(tp_match.group(1))
            
        return signal
        
    # Mode 4: General Advice (Low Confidence)
    # Pattern: "建议在4.25元附近买入..." or "建议买入..."
    # Search for "建议" sentence
    suggestion_match = re.search(r"建议.*?([买卖].*?)[。！\n]", content)
    if suggestion_match:
        s_text = suggestion_match.group(1)
        
        # Action
        if any(w in s_text for w in ["买", "吸", "接", "做多"]):
             signal.action = "buy"
        elif any(w in s_text for w in ["卖", "出", "减", "清"]):
             signal.action = "sell"
        else:
             return signal
             
        # Price
        prices = re.findall(r"(\d+\.\d{2})", s_text)
        if prices:
            signal.price_target = float(prices[0])
            
        # Quantity (e.g. 37000股)
        qty_match = re.search(r"(\d+)股", s_text)
        if qty_match:
            signal.quantity = int(qty_match.group(1))
            
        # SL/TP checks (GLOBAL)
        if signal.stop_loss == 0:
             sl_match = re.search(r"(?:止损|防守).*?(\d+\.\d{2})", content)
             if sl_match: signal.stop_loss = float(sl_match.group(1))
             
        return signal
