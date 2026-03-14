# A股智能盯盘与辅助交易系统 (AShare-Monitor) v3.2.0

这是一个基于 Streamlit 构建的 **AI 驱动型** A 股辅助决策系统。v3.2.0 统一了提示词管理，将所有硬编码提示词迁移至提示词中心，实现可配置、可热更新的提示词管理。

## 核心功能 (Core Features)

- **⚔️ 蓝军军团 (Blue Legion MoE)**: 
  - **数学官 (Quant Agent)**: 深度分析资金流向、分时盘口与盈亏比。
  - **情报官 (Intel Agent)**: 全网聚合 RAG 情报，回溯历史战绩与新闻叙事。
  - **主帅 (Commander)**: 月之暗面 Kimi-K2.5 模型统筹决策，签署最终交易令 (GTO 策略)。
- **🛡️ 红军风控 (Red Audit)**: 
  - 默认集成 **DeepSeek-R1 (Reasoner)**，对蓝军策略进行 "攻击性审计"，识别逻辑漏洞与主要风险。
  - 独创 "Draft -> Audit -> Refine -> Verdict -> Final Order" 五步闭环决策流。
- **🔍 智能情报 (Intelligence)**: 
  - 使用 **Qwen (DashScope)** 的联网搜索能力，搜集市场情报和研报信息。
  - Qwen 仅用于情报搜索，不参与策略生成或审计。
- **⚡ 极速模式 (Auto-Drive)**: 
  - 一键全自动执行 "生成草案-风险初审-反思优化-终极裁决-签署命令" 全流程，仅需数秒即可完成深度复盘。
  - **蓝军 (Kimi-k2.5)**: 策略生成与优化
  - **红军 (DeepSeek-R1)**: 风险审计与终端裁决
- **实时盯盘**: 分秒级监控自选股，智能缓存拒绝流量浪费，非交易时间自动休眠。
- **提示词中心**: 模块化管理 AI 人格设定，内置 "午间复盘"、"盘前规划" 等专业场景模版。

## 快速开始

### 环境依赖
- Python 3.8+
- API Keys: 
  - **DeepSeek** (红军审计官)
  - **Kimi/Moonshot** (蓝军主帅 - 主模型)
  - **DashScope/Qwen** (仅用于情报搜索)
  - Metaso (可选，用于深度研报)

### 安装与运行 (Linux/Mac)
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
./scripts/start.sh
# 或
python main.py
```

### 初始化配置
1. 打开侧边栏 (Sidebar)。
2. 填入 API Key：
   - **Kimi API Key** (必填): 用于蓝军策略生成
   - **DeepSeek API Key** (必填): 用于红军风控审计
   - **Qwen API Key** (可选): 仅用于情报搜索
3. 添加自选股代码 (如 `600076`)。
4. 开含 `⚡ Auto-Drive` 体验军团作战。

## 项目结构
```
├── main.py                 # 主程序入口
├── components/             # UI 组件 (策略区、仪表盘、实验室)
├── utils/                  # 工具函数
│   ├── legion_advisor.py   # 蓝军军团 (MoE) 核心逻辑
│   ├── ai_advisor.py       # AI 接口封装
│   ├── intel_manager.py    # 智能情报 RAG 系统
│   ├── prompt_loader.py    # Markdown 提示词加载器
│   └── data_fallback.py    # 备用数据源 (Sina/Tencent)
├── scripts/                # 脚本工具 (启动/停止/部署)
├── prompts/                # Markdown 格式 AI 提示词
├── stock_data/             # 本地行情缓存
├── docs/                   # 项目文档
│   ├── v4.1_ROADMAP.md     # v4.1 开发路线图
│   └── v4.1_STATUS.md      # 项目状态
└── PROJECT_STRUCTURE.md    # 完整目录说明
```

## 开发协议 (Development Protocol)

为维护长期可维护性，本项目严格遵循以下更新策略：
1.  **版本同步**: `VERSION` 变动时，必须同步更新 `CHANGELOG.md` (详细日志) 和 `README.md` (功能摘要)。
2.  **README 对齐**: `README.md` 必须反映当前版本的核心架构，严禁保留误导性的旧版本描述。
3.  **双模一致**: 无论是 Auto-Drive 还是 Manual 模式，底层必须调用相同的业务逻辑函数 (如 `run_blue_legion`)。
4.  **提示词管理**: v2.8.0+ 所有提示词统一放在 `prompts/` 目录，以 Markdown 格式管理，通过 `utils/prompt_loader.py` 加载。严禁将提示词硬编码在 Python 文件中。
