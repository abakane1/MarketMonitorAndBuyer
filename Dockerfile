# 优化的 Dockerfile - 快速构建版本
FROM python:3.11-slim as builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖（利用缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产阶段
FROM python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai
ENV PATH=/root/.local/bin:$PATH

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /root/.local /root/.local

# 创建数据目录
RUN mkdir -p /app/data /app/logs /app/stock_data

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 启动命令
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
