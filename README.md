# A股智能盯盘与辅助交易系统 (A-Share Monitor & AI Advisor)

这是一个基于 Streamlit 构建的综合性 A 股盯盘与辅助决策系统，集成了 DeepSeek、Gemini 和 Metaso 等先进 AI 模型，为投资者提供实时的市场研判、情报分析及交易建议。

## 核心功能

- **实时盯盘**: 支持同时监控多达 5 只自选股/ETF，提供秒级价格刷新（智能缓存机制）。
- **AI 联合研判**: 独创 "DeepSeek (逻辑/策略) + Metaso (情报/消息)" 联合诊断模式，模拟 "GTO 德州扑克" 交易思维提供操作建议。
- **智能情报中心**: 全网聚合最新利好利空消息，自动去重、标记真伪。支持 "闭盘模式"，优先读取本地离线情报。
- **策略引擎**: 内置 "筹码分布 (Volume Profile)" 策略，精准识别 "底池 (支撑)" 和 "对手盘 (阻力)"。
- **持仓管理**: 记录持仓成本、浮动盈亏，在此基础上计算合理的 "下注比例 (Bet Size)"。
- **智能数据同步**: 具备休市检测功能，在非交易时间自动冻结 API 请求，优先使用本地缓存数据，拒绝流量浪费。

## 快速开始

    ### macOS / Linux
    ```bash
    # 1. 安装依赖
    pip install -r requirements.txt
    
    # 2. 启动应用
    ./start.sh
    ```

    ### Windows
    ```powershell
    # 1. 创建虚拟环境 (推荐)
    python -m venv venv
    
    # 2. 激活环境并安装依赖
    .\venv\Scripts\pip install -r requirements.txt
    
    # 3. 启动应用
    .\venv\Scripts\streamlit run main.py
    ```

3.  **初始化配置**:
    - 打开侧边栏 (Sidebar)。
    - 填入您的 **DeepSeek API Key** 和 **Metaso API Key**。
    - 设置 **初始本金 (Total Capital)**。
    - 添加需监控的股票代码 (如 `600076` 或 `588000`)。

## 项目结构

- `main.py`: 主程序入口及 UI 交互逻辑。
- `utils/strategy.py`: 量化策略核心 (筹码分布 & GTO 仓位管理)。
- `utils/ai_advisor.py`: DeepSeek / Gemini AI 接口封装。
- `utils/researcher.py`: Metaso 联网搜索接口 (含缓存)。
- `utils/intel_manager.py`: 情报数据库管理 (SQLite)。
- `utils/database.py`: 数据库访问层 (CRUD)。
- `utils/data_fetcher.py`: AkShare 数据获取封装。
- `user_data.db`: 核心业务数据库 (存储持仓、情报、策略历史、配置)。
- `stock_data/`: 存放本地行情缓存 (Parquet)。

## 注意事项

- **数据源**: 行情数据由 [AkShare](https://github.com/akfamily/akshare) 提供。
- **隐私安全**: 所有 API Key 和交易记录均仅保存在本地 `user_config.json` 和 `user_data.db` 中，绝不上传云端。

