#!/bin/bash
# MarketMonitorAndBuyer 启动脚本
# 支持前台运行或后台守护进程模式

PROJECT_DIR="$HOME/MarketMonitorAndBuyer"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$LOG_DIR/streamlit.pid"

# 创建日志目录
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  服务已在运行 (PID: $PID)"
        echo "🌐 访问地址: http://localhost:8501"
        exit 0
    fi
fi

echo "🚀 启动 MarketMonitorAndBuyer..."
echo "📁 项目目录: $PROJECT_DIR"
echo "📝 日志文件: $LOG_DIR/streamlit.log"

# 激活虚拟环境
source "$PROJECT_DIR/venv/bin/activate"

# 启动 Streamlit
nohup streamlit run main.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    > "$LOG_DIR/streamlit.log" 2>&1 &

# 保存 PID
echo $! > "$PID_FILE"

sleep 2

# 检查是否启动成功
if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
    echo "✅ 启动成功！"
    echo "🌐 访问地址: http://localhost:8501"
    echo "📊 批量策略页面: http://localhost:8501/03_批量策略"
else
    echo "❌ 启动失败，请检查日志: $LOG_DIR/streamlit.log"
    exit 1
fi
