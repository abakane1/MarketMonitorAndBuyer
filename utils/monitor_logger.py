# -*- coding: utf-8 -*-
"""
AI 监控日志记录器
用于持久化 AI 的思考状态、心跳和决策，供前台监控组件读取。
"""
import json
import os
from datetime import datetime
import threading

MONITOR_STATE_FILE = "stock_data/monitor_state.json"
_lock = threading.Lock()

def log_ai_heartbeat(code: str, decision: str, reason: str, sentiment: str = "Neutral", duration: float = 0.0):
    """
    记录 AI 的心跳状态。
    
    Args:
        code: 股票代码
        decision: 决策 (买入/卖出/观望)
        reason: 简短理由
        sentiment: 情绪 (Fear/Greed/Neutral)
        duration: 思考耗时(秒)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = {
        "timestamp": timestamp,
        "decision": decision,
        "reason": reason,
        "sentiment": sentiment,
        "duration": f"{duration:.1f}s"
    }
    
    with _lock:
        data = {}
        if os.path.exists(MONITOR_STATE_FILE):
            try:
                with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = {}
        
        # Update latest state for this stock
        if "latest" not in data:
            data["latest"] = {}
        data["latest"][code] = entry
        
        # Append to log stream (global or per stock? let's keep a short global log)
        if "logs" not in data:
            data["logs"] = []
            
        log_msg = f"[{timestamp}] [{code}] {decision}: {reason[:50]}..."
        data["logs"].insert(0, log_msg)
        # Keep only last 50 logs
        data["logs"] = data["logs"][:50]
        
        # Save
        try:
            # Ensure dir exists
            os.makedirs(os.path.dirname(MONITOR_STATE_FILE), exist_ok=True)
            with open(MONITOR_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save monitor state: {e}")

def get_ai_monitor_state(code: str = None):
    """
    获取监控状态。
    """
    if not os.path.exists(MONITOR_STATE_FILE):
        return None
        
    try:
        with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if code:
            return data.get("latest", {}).get(code), data.get("logs", [])
        return data
    except:
        return None
