#!/bin/bash
# Docker 部署脚本 for MarketMonitorAndBuyer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 MarketMonitorAndBuyer Docker 部署脚本"
echo "========================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "   安装指南: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    echo "   安装指南: https://docs.docker.com/compose/install/"
    exit 1
fi

# 函数：构建镜像
build() {
    echo "📦 构建 Docker 镜像..."
    docker-compose build --no-cache
    echo "✅ 镜像构建完成"
}

# 函数：启动服务
start() {
    echo "▶️ 启动服务..."
    docker-compose up -d
    echo "✅ 服务已启动"
    echo ""
    echo "🌐 访问地址: http://localhost:8501"
    echo "📊 批量策略页面: http://localhost:8501/03_批量策略"
}

# 函数：停止服务
stop() {
    echo "⏹️ 停止服务..."
    docker-compose down
    echo "✅ 服务已停止"
}

# 函数：重启服务
restart() {
    echo "🔄 重启服务..."
    docker-compose restart
    echo "✅ 服务已重启"
}

# 函数：查看日志
logs() {
    echo "📋 查看日志..."
    docker-compose logs -f --tail=100
}

# 函数：更新代码并重启
update() {
    echo "⬇️ 拉取最新代码..."
    git pull origin main
    echo "📦 重新构建镜像..."
    docker-compose build
    echo "🔄 重启服务..."
    docker-compose up -d
    echo "✅ 更新完成"
}

# 函数：查看状态
status() {
    echo "📊 服务状态:"
    docker-compose ps
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
    
    # 检查 .secret.key
    if [ ! -f .secret.key ]; then
        echo "⚠️ 警告: .secret.key 不存在，某些功能可能无法正常工作"
        echo "   请确保配置了正确的 API 密钥"
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
}

# 主命令处理
case "${1:-deploy}" in
    build)
        build
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
    deploy|*)
        deploy
        ;;
esac
