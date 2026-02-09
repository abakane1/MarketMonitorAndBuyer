# A股智能盯盘与辅助交易系统 (AShare-Monitor) v2.7.1

这是一个基于 Streamlit 构建的 **AI 驱动型** A 股辅助决策系统。v2.7.1 在 **"Blue Legion (蓝军军团)"** 混合专家架构 (MoE) 基础上进一步强化了环境鲁棒性与数据稳定性。

## 核心功能 (Core Features)

- **⚔️ 蓝军军团 (Blue Legion MoE)**: 
  - **数学官 (Quant Agent)**: 深度分析资金流向、分时盘口与盈亏比。
  - **情报官 (Intel Agent)**: 全网聚合 RAG 情报，回溯历史战绩与新闻叙事。
  - **主帅 (Commander)**: 阿里 Qwen-Max 模型统筹决策，签署最终交易令 (GTO 策略)。
- **🛡️ 红军风控 (Red Audit)**: 
  - 默认集成 **DeepSeek-R1 (Reasoner)**，对蓝军策略进行 "攻击性审计"，识别逻辑漏洞与主要风险。
  - 独创 "Draft -> Audit -> Refine -> Verdict -> Final Order" 五步闭环决策流。
- **⚡ 极速模式 (Auto-Drive)**: 
  - 一键全自动执行 "生成草案-风险初审-反思优化-终极裁决-签署命令" 全流程，仅需数秒即可完成深度复盘。
- **实时盯盘**: 分秒级监控自选股，智能缓存拒绝流量浪费，非交易时间自动休眠。
- **提示词中心**: 模块化管理 AI 人格设定，内置 "午间复盘"、"盘前规划" 等专业场景模版。

## 快速开始

### 环境依赖
- Python 3.8+
- API Keys: DeepSeek, DashScope (Qwen), Metaso (Optional)

### 安装与运行 (Linux/Mac)
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
./start.sh
```

### 初始化配置
1. 打开侧边栏 (Sidebar)。
2. 填入 API Key (推荐同时配置 DeepSeek 与 Qwen 以解锁完整 MoE 能力)。
3. 添加自选股代码 (如 `600076`)。
4. 开启 `⚡ Auto-Drive` 体验军团作战。

## 项目结构
- `main.py`: 主程序 UI 入口。
- `components/`: UI 组件拆分 (策略区、仪表盘、实验室)。
- `utils/legion_advisor.py`: **[New]** 蓝军军团 (MoE) 核心逻辑。
- `utils/ai_advisor.py`: AI 接口封装 (DeepSeek/Qwen 动态调度)。
- `utils/intel_manager.py`: 智能情报 RAG 系统。
- `stock_data/`: 本地行情缓存 (Parquet)。

## 开发协议 (Development Protocol)

为维护长期可维护性，本项目严格遵循以下更新策略：
1.  **版本同步**: `VERSION` 变动时，必须同步更新 `CHANGELOG.md` (详细日志) 和 `README.md` (功能摘要)。
2.  **README 对齐**: `README.md` 必须反映当前版本的核心架构 (如 v2.7.1 的环境自修复与 MoE 机制)，严禁保留误导性的旧版本描述。
3.  **双模一致**: 无论是 Auto-Drive 还是 Manual 模式，底层必须调用相同的业务逻辑函数 (如 `run_blue_legion`)。
