#!/bin/bash
# MarketMonitorAndBuyer 卸载开机自启脚本

echo "🧹 MarketMonitorAndBuyer 卸载开机自启"
echo "======================================"

PLIST_DEST="$HOME/Library/LaunchAgents/com.marketmonitor.autostart.plist"

# 停止服务
if launchctl list | grep -q "com.marketmonitor.autostart"; then
    echo "🛑 停止服务..."
    launchctl stop com.marketmonitor.autostart
    sleep 1
fi

# 卸载配置
if [ -f "$PLIST_DEST" ]; then
    echo "🔧 卸载启动配置..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm "$PLIST_DEST"
fi

# 停止运行中的服务
$HOME/MarketMonitorAndBuyer/stop.sh 2>/dev/null || true

echo ""
echo "✅ 卸载完成！"
echo "ℹ️  开机自动启动已禁用"
