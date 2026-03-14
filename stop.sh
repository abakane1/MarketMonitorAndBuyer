#!/bin/bash
# MarketMonitorAndBuyer 停止脚本

PROJECT_DIR="$HOME/MarketMonitorAndBuyer"
PID_FILE="$PROJECT_DIR/logs/streamlit.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 停止服务 (PID: $PID)..."
        kill "$PID"
        rm "$PID_FILE"
        echo "✅ 已停止"
    else
        echo "⚠️  服务未在运行"
        rm "$PID_FILE"
    fi
else
    echo "⚠️  未找到 PID 文件，尝试查找进程..."
    PID=$(pgrep -f "streamlit run main.py")
    if [ -n "$PID" ]; then
        echo "🛑 找到进程 (PID: $PID)，正在停止..."
        kill "$PID"
        echo "✅ 已停止"
    else
        echo "ℹ️  没有找到运行中的服务"
    fi
fi
