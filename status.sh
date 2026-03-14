#!/bin/bash
# MarketMonitorAndBuyer 状态检查脚本

PROJECT_DIR="$HOME/MarketMonitorAndBuyer"
PID_FILE="$PROJECT_DIR/logs/streamlit.pid"

echo "📊 MarketMonitorAndBuyer 状态检查"
echo "=================================="

# 检查 PID 文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "📝 PID 文件: $PID_FILE"
    echo "🔢 记录 PID: $PID"
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ 服务正在运行"
        echo "🌐 访问地址: http://localhost:8501"
        echo ""
        echo "💻 进程信息:"
        ps -p "$PID" -o pid,ppid,%cpu,%mem,etime,command
        echo ""
        echo "📈 资源使用:"
        top -pid "$PID" -l 1 | tail -1
    else
        echo "❌ 服务未运行 (PID 文件过期)"
        rm "$PID_FILE"
    fi
else
    echo "⚠️  未找到 PID 文件"
    
    # 尝试查找进程
    PID=$(pgrep -f "streamlit run main.py")
    if [ -n "$PID" ]; then
        echo "🔍 找到运行中的进程 (PID: $PID)"
        echo "🌐 访问地址: http://localhost:8501"
    else
        echo "ℹ️  服务未运行"
    fi
fi

echo ""
echo "📋 最近日志:"
tail -n 5 "$PROJECT_DIR/logs/streamlit.log" 2>/dev/null || echo "暂无日志"
