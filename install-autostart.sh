#!/bin/bash
# MarketMonitorAndBuyer 开机自启安装脚本

echo "🚀 MarketMonitorAndBuyer 开机自启安装"
echo "======================================"

PLIST_SOURCE="$HOME/MarketMonitorAndBuyer/scripts/com.marketmonitor.autostart.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.marketmonitor.autostart.plist"

# 检查源文件
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "❌ 错误: 找不到启动配置文件"
    echo "   $PLIST_SOURCE"
    exit 1
fi

# 给脚本添加执行权限
chmod +x "$HOME/MarketMonitorAndBuyer/start.sh"
chmod +x "$HOME/MarketMonitorAndBuyer/stop.sh"
chmod +x "$HOME/MarketMonitorAndBuyer/status.sh"

# 复制 plist 文件
echo "📋 安装启动配置..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# 加载配置
echo "🔧 加载启动服务..."
launchctl load "$PLIST_DEST"

# 启动服务
echo "▶️  启动服务..."
launchctl start com.marketmonitor.autostart

sleep 2

# 检查状态
if launchctl list | grep -q "com.marketmonitor.autostart"; then
    echo ""
    echo "✅ 安装成功！"
    echo ""
    echo "📖 常用命令:"
    echo "   ./start.sh       # 手动启动"
    echo "   ./stop.sh        # 停止服务"
    echo "   ./status.sh      # 查看状态"
    echo "   ./uninstall-autostart.sh  # 卸载自启"
    echo ""
    echo "🌐 访问地址: http://localhost:8501"
    echo "🔄 已设置开机自动启动"
else
    echo "⚠️  安装可能有问题，请检查日志"
fi
