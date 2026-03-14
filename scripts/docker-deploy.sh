#!/bin/bash
# 优化的 Docker 部署脚本 for MarketMonitorAndBuyer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 MarketMonitorAndBuyer Docker 部署脚本 (优化版)"
echo "=================================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "   安装指南: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose 未安装"
    exit 1
fi

# 函数：构建镜像（使用缓存）
build() {
    echo "📦 构建 Docker 镜像（使用缓存加速）..."
    
    # 先尝试拉取缓存镜像
    docker pull market-monitor:latest 2>/dev/null || true
    
    # 构建镜像
    $COMPOSE_CMD build --parallel
    
    echo "✅ 镜像构建完成"
}

# 函数：快速构建（开发模式）
build-quick() {
    echo "📦 快速构建（跳过部分优化）..."
    docker build -t market-monitor:latest -f Dockerfile.quick .
    echo "✅ 快速构建完成"
}

# 函数：启动服务
start() {
    echo "▶️ 启动服务..."
    $COMPOSE_CMD up -d
    echo "✅ 服务已启动"
    echo ""
    echo "🌐 访问地址: http://localhost:8501"
    echo "📊 批量策略页面: http://localhost:8501/03_批量策略"
}

# 函数：停止服务
stop() {
    echo "⏹️ 停止服务..."
    $COMPOSE_CMD down
    echo "✅ 服务已停止"
}

# 函数：重启服务
restart() {
    echo "🔄 重启服务..."
    $COMPOSE_CMD restart
    echo "✅ 服务已重启"
}

# 函数：查看日志
logs() {
    echo "📋 查看日志..."
    $COMPOSE_CMD logs -f --tail=100
}

# 函数：更新代码并重启
update() {
    echo "⬇️ 拉取最新代码..."
    git pull origin main
    echo "📦 重新构建镜像..."
    build
    echo "🔄 重启服务..."
    $COMPOSE_CMD up -d
    echo "✅ 更新完成"
}

# 函数：查看状态
status() {
    echo "📊 服务状态:"
    $COMPOSE_CMD ps
    echo ""
    echo "💻 系统资源使用:"
    docker stats --no-stream market-monitor-and-buyer 2>/dev/null || echo "   服务未运行"
}

# 函数：初始化配置
init() {
    echo "🔧 初始化配置..."
    
    # 创建必要的目录
    mkdir -p data logs stock_data
    
    # 创建空的队列文件（如果不存在）
    if [ ! -f strategy_queue.json ]; then
        echo "[]" > strategy_queue.json
    fi
    
    # 创建默认关注列表（如果不存在）
    if [ ! -f watchlist.json ]; then
        echo '[{"code": "588710", "name": "科创50ETF", "priority": 1}]' > watchlist.json
    fi
    
    echo "✅ 初始化完成"
}

# 函数：一键部署（首次使用）
deploy() {
    echo "🎯 开始一键部署..."
    init
    build
    start
    echo ""
    echo "🎉 部署完成！"
    echo "========================================"
    echo "🌐 访问地址: http://localhost:8501"
    echo "📊 批量策略页面: http://localhost:8501/03_批量策略"
    echo ""
    echo "📖 常用命令:"
    echo "   ./docker-deploy.sh stop    # 停止服务"
    echo "   ./docker-deploy.sh start   # 启动服务"
    echo "   ./docker-deploy.sh logs    # 查看日志"
    echo "   ./docker-deploy.sh update  # 更新代码"
    echo ""
    echo "🚀 设置开机自动启动:"
    echo "   cp scripts/com.marketmonitor.autostart.plist ~/Library/LaunchAgents/"
    echo "   launchctl load ~/Library/LaunchAgents/com.marketmonitor.autostart.plist"
}

# 函数：清理
 clean() {
    echo "🧹 清理未使用的镜像和缓存..."
    docker system prune -f
    echo "✅ 清理完成"
}

# 主命令处理
case "${1:-deploy}" in
    build)
        build
        ;;
    build-quick)
        build-quick
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    update)
        update
        ;;
    status)
        status
        ;;
    init)
        init
        ;;
    clean)
        clean
        ;;
    deploy|*)
        deploy
        ;;
esac
