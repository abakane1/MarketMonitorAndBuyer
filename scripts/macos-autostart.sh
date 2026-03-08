#!/bin/bash
# macOS 开机自动启动脚本

# MarketMonitorAndBuyer 开机自动启动配置
# 安装方法：
# 1. 复制此文件到 ~/Library/LaunchAgents/com.marketmonitor.autostart.plist
# 2. 运行: launchctl load ~/Library/LaunchAgents/com.marketmonitor.autostart.plist
# 3. 运行: launchctl start com.marketmonitor.autostart

PROJECT_DIR="$HOME/MarketMonitorAndBuyer"
LOG_FILE="$PROJECT_DIR/logs/docker-autostart.log"

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/logs"

echo "[$(date)] 检查 Docker 状态..." >> "$LOG_FILE"

# 等待 Docker Desktop 启动（最多等60秒）
for i in {1..60}; do
    if docker info >/dev/null 2>&1; then
        echo "[$(date)] Docker 已就绪" >> "$LOG_FILE"
        break
    fi
    echo "[$(date)] 等待 Docker 启动... ($i/60)" >> "$LOG_FILE"
    sleep 1
done

# 启动服务
echo "[$(date)] 启动 MarketMonitorAndBuyer..." >> "$LOG_FILE"
cd "$PROJECT_DIR"
./docker-deploy.sh start >> "$LOG_FILE" 2>&1

echo "[$(date)] 启动完成" >> "$LOG_FILE"
