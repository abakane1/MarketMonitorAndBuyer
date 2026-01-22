# Changelog

All notable changes to the **MarketMonitorAndBuyer** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.2] - 2026-01-22 (Strategy UI Split)
### Changed (优化)
- **策略入口分离 (Button Split)**: 
  - 废弃了 v1.4.1 的自动切换逻辑，改为显式的“双按钮”设计：
    - `💡 生成盘前策略`: 适用于每日复盘与计划。
    - `⚡ 生成盘中对策`: 适用于盘中突发决策。
- **误操作警示 (Safe Guard)**: 
  - 当用户在休市时间点击“盘中对策”或在开盘时间点击“盘前策略”时，系统会在提示词预览界面弹出**黄色警告**，防止误用过期/未来数据，但保留了强制执行的权利。
- **提示词中心更新**: 
  - 更新了提示词文档描述，明确了“盘前”与“盘中”的区别，并标记旧版“验证后缀”为已弃用。

## [1.4.1] - 2026-01-22 (Intra-day Strategy Split)
### Added (新增)
- **动态策略路由 (Dynamic Strategy Routing)**: 
  - 根据 A 股交易时间 (09:15-11:30, 13:00-15:05) 自动切换 AI 模式。
  - **盘中模式 (Intra-day)**: 按钮变为 "⚡ 生成盘中对策"，调用专用的 `deepseek_intraday_suffix`，专注于实时盘口分析与超短线决策。
  - **盘前模式 (Pre-market)**: 按钮保持 "💡 生成盘前策略"，专注于全天计划制定。
- **Intra-day Prompt**: 新增了针对盘中突发决策的提示词模板，强调“极窄止损”和“即时买卖”。

## [1.4.0] - 2026-01-22 (AI Feedback Loop & Safe Guard)
### Added (新增)
- **AI 闭环反馈 (AI Feedback Loop)**: 
  - 自动注入用户真实成交记录 (`User Execution`) 到 DeepSeek 历史研判上下文中。
  - Prompt 升级：DeepSeek 现可对用户的执行力进行评价 ("Reflection & Eval")，实现从“单向建议”到“双向监督”的进化。
- **提示词预览 (Prompt Preview)**: 
  - 生成策略前新增预览确认环节，支持查看完整 Prompt 内容及 Token 估算，确保发送内容透明可控。
- **数据关联 (Trade Matching)**: 
  - 历史研报记录中现可直接展示该时间段内的关联交易 (Actual Trades)，直观对比“AI建议”与“实际操作”。

### Fixed (修复)
- **精准涨跌停计算**: 
  - 修复 `pre_close` 获取逻辑，基于名为规则 (ST/科创/北交所) 动态计算当日涨跌停价，防止 AI 产生幻觉报价。
  - 增加对 AkShare 实时接口 `pre_close` 缺失的健壮性回退机制 (Fallback to Daily History)。
- **策略清洗**: 增加了清理错误日期策略的工具脚本。

## [1.3.0] - 2026-01-19 (Architecture Refactoring & Testing)
### Added (新增)
- **组件化架构**: 新增 `components/` 目录，将侧边栏逻辑拆分至 `sidebar.py`，提升代码可维护性。
- **Pytest 测试框架**: 引入标准化测试体系，覆盖 `strategy.py` 和 `data_fetcher.py` 核心逻辑。
- **自定义异常类**: 新增 `DataFetchError`、`DataParseError`、`DataNotFoundError` 异常类，细化错误处理。
- **日志系统**: 在 `data_fetcher.py` 中集成 `logging` 模块，替代 `print` 语句。

### Changed (优化)
- **动态日期选择**: `sim_ui.py` 回测模块消除硬编码日期 `"2026-01-19"`，支持用户选择任意可用交易日。
- **错误处理增强**: 区分网络连接错误、API 数据解析错误等场景，提供更清晰的错误信息。

### Tests (测试)
- 新增 `tests/conftest.py` 共享 fixtures
- 新增 `tests/test_strategy.py` (10 个测试用例)
- 新增 `tests/test_data_fetcher.py` (13 个测试用例)

## [1.2.2] - 2026-01-19 (Prompt Management & UI Logic Fix)
### Added (新增)
- **提示词中心**: 在侧边栏新增“提示词中心”导航，支持分类查看系统中使用的所有 AI 提示词模板。

### Fixed (修复)
- **UI 重复问题**: 修复了由于缩进错误导致的功能模块（AI 研判、情报数据库等）在主页底部重复渲染的问题。
- **结构性故障**: 修复了 `update_view` 函数由于逻辑分支不一致导致的 `NameError`。
- **布局优化**: 将交易历史记录表格移入“交易记账”折叠面板内部，并统一使用了 `use_container_width` 提升对齐美感。

## [1.2.1] - 2026-01-19 (Research Workflow Decoupling)
### Changed (优化)
- **流程重构**: 将秘塔深度研究从 AI 研判流程中剥离，使其成为情报数据库的可选操作。
- **效率提升**: AI 深度研判现在直接基于已有情报库生成策略，生成速度显著提升。
- **UI 调整**: 秘塔搜索按钮已移至 "🗃️ 股票情报数据库 (Intelligence Hub)" 中。

## [1.1.1] - 2026-01-19 (UI Polish & Stability Update)
### Added (新增)
- **隐私保护**: 持仓看板现支持点击折叠，默认隐藏以保护隐私。

### ✨ 优化功能 (Improved Features)
- **建议显示优化**：将 AI 建议中的长文本注释（如仓位解释）从主体指标中分离，单独以小字注释形式显示，解决显示不全的问题。
- **UI 布局压缩**：进一步缩小按钮尺寸并压缩分割线间距，提升界面信息密度。
- **UI 增强**: AI 深度研判与算法建议布局优化，逻辑层级更清晰。

### Fixed (修复)
- **算法逻辑**: 修正了部分买入信号下头寸计算为负数的 Bug。
- **实时刷新**: 修复了 AI 策略生成后 UI 不会自动更新的问题。

## [1.1.0] - 2026-01-18 (Intelligence Era Update)
### Added (新增)
- **AI 独立策略看板**: 新增 "🧠 AI Independent Strategy" 标签页，提供基于 DeepSeek Reasoner 的独立交易建议 (v1.1.0)。
- **情报去重系统**: 新增交互式数据清洗功能 (`Deduplication`)，支持 AI 语义去重和人工确认。
- **SQLite 数据库集成**: 持仓/资金/历史数据迁移至 SQLite，提升稳定性。
- **全量情报上下文**: 解除 DeepSeek 历史情报回溯限制，引入 `get_claims_for_prompt(None)`。

### Changed (优化)
- **核心逻辑**: 将情报归档维度从“采集时间”重构为“事件发生时间”。
- **提示词工程**: 增加 `capital_allocation` (资金硬约束) 和 `Independent Warning` (独立性警告)。
- **UI 体验**: 策略看板支持自动解析“方向/仓位/止损”并图形化展示。

### Fixed (修复)
- 修复 `dict` 类型情报导致的哈希错误。
- 修复 `UnboundLocalError` 及情报过滤缩进问题。

## [1.0.7] - 2026-01-17 (Deep Research & Precision Update)
### Added (新增)
- **秘塔深度研究 (Deep Research)**: 
  - 集成 `ask_metaso_research_loop`，支持多轮追问与关联搜索。
  - 引入 `metaso_parser`，自动从研报中提取结构化事实 (`claims`)。
- **双模策略引擎**: 
  - 引入 Gemini 作为“第二意见” (Second Opinion) 与 DeepSeek 形成红蓝对抗。
  - 支持 `deepseek-reasoner` 思考模型集成。
- **ETF 动态精度**: 
  - 支持 ETF (3位小数) 与股票 (2位小数) 的动态价格精度显示与计算。

### Changed (优化)
- **配置重构**: 将所有 AI Prompt 从代码硬编码迁移至 `user_config.json`，支持热更新。
- **资金分配**: `user_config.json` 新增 `allocations` 字段，支持单股资金限额配置。

## [1.0.0] - 2026-01-16 (Initial Release)
### Released
- 🚀 **主要功能**:
  - A股实时行情监控 (基于 SINA/EM API)。
  - 基础筹码分布策略 (Volume Profile Strategy)。
  - 简单的 Streamlit 可视化大屏。
  - 基础的 `intelligence.json` 数据结构。
