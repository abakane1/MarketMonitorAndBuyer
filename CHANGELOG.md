# Changelog

All notable changes to the **MarketMonitorAndBuyer** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-01-22 (DeepSeek Engine Evolution)
### Changed (核心升级)
- **提示词工程重构 (Prompt Refactor)**:
  - **结构分离**: 将 Prompt 拆分为 **System Prompt** (负责 LAG+GTO 哲学/人设) 与 **User Prompt** (负责数据输入)，大幅降低了模型认知负担。
  - **逻辑进化**: 盘前策略目标从“打败算法”升级为“**人机合一 (Synthesis)**”，强调结合算法信号进行独立博弈，并新增“承前启后”指令以确保策略连续性。
- **反幻觉机制 (Anti-Hallucination)**:
  - **RAG 优化**: 历史研判回溯仅提取**【决策摘要】**并强制锚定【实时价格】，彻底消除了 AI 被历史旧价格误导的风险。
  - **信号明确化**: 将算法建议明确标记为 `[Algo Pending Order]`，防止 AI 将其误读为“用户已执行”。
- **执行评价修正**: 修复了 AI 因“单笔买入量”小而误判用户执行力的 Bug，现强制按**累计总仓位**进行考核。

### Fixed (修复)
- **精准风控**: 
  - 修复了科创板 ETF (588) 涨跌幅识别错误 (20%)。
  - 引入 A 股标准四舍五入算法，消除了 1 分钱报价误差。
  - 修复了“盘前策略”在晚间生成时错误使用“昨日收盘价”计算明日涨跌停的问题。
- **UI/UX 改进**:
  - 策略入口分离为“💡 盘前计划”与“⚡ 盘中对策”双模式。
  - 历史记录自动打标策略类型，并在非交易时段提供误操作警示。

## [1.4.0] - 2026-01-22 (Interactive Strategy System)
### Added (新增)
- **AI 闭环反馈 (feedback Loop)**: AI 现可读取用户的**真实成交记录**，并在历史复盘中对用户的执行力进行评价 ("Reflection & Eval")，实现了“建议-执行-复盘”的完整闭环。
- **动态策略路由 (Dynamic Routing)**: 
  - 根据交易时间段自动切换模式：盘中(09:30-15:00) 聚焦“⚡ 盘中对策 (超短线)”；盘后 聚焦“💡 盘前计划 (波段)”。
  - 针对盘中场景新增了专用 Prompt，强调“极窄止损”和“即时决策”。
- **交互安全**: 新增 Prompt 预览确认环节，支持查看 Token 消耗预估；在历史研报中展示关联交易记录。

### Fixed (修复)
- **价格幻觉修复**: 修复了 `pre_close` 获取逻辑，基于名为规则 (ST/科创/北交所) 动态计算当日涨跌停价，防止 AI 针对已涨停股票继续给出买入建议。

## [1.3.0] - 2026-01-19 (Infrastructure Refactoring)
### Added (新增)
- **工程化架构**: 
  - 引入 `components/` 目录将 UI 逻辑解耦；新增 **Prompt Center** (提示词中心) 面板，支持可视化管理所有 AI 模板。
  - 引入标准化 **Pytest** 测试框架与自动化日志系统 (`monitor_logger`)，替代了不稳定的 `print` 调试。
- **配置管理**: 
  - 将所有硬编码 Prompt 全部迁移至 `user_config.json`，支持无需重启的热更新。
  - 新增 `allocations` 字段，支持为每只股票单独配置资金上限 (Capital Allocation)。

### Fixed (修复)
- 解决了主页底部 UI 模块重复渲染的严重 Bug；修复了回测模块的动态日期选择问题。

## [1.2.0] - 2026-01-18 (The Intelligence Era)
### Added (新增)
- **情报数据库 (Intelligence Hub)**: 
  - 集成 **SQLite** 数据库，将情报归档维度重构为“事件发生时间”，支持全量情报的持久化存储与检索。
  - 新增交互式“情报去重系统” (`Deduplication`)，支持 AI 语义去重。
- **深度研判引擎 (Deep Research)**: 
  - 集成 **Metaso (秘塔)** 深度搜索接口，支持多轮追问与关联搜索；引入 `metaso_parser` 自动提取结构化事实 (`claims`)。
  - 引入 **Gemini** 作为“第二意见 (Second Opinion)”，与 DeepSeek 形成红蓝对抗机制。
- **双模与可视化**: 
  - 新增全独立的“🧠 AI Independent Strategy”看板。
  - 策略建议支持图形化展示（方向/仓位/止损可视化仪表盘）。

### Changed (优化)
- **流程解耦**: 将“搜集情报”与“生成策略”解耦，大幅提升了生成速度。
- **ETF 适配**: 支持 ETF (3位小数) 与股票 (2位小数) 的动态精度显示。

## [1.0.0] - 2026-01-16 (Genesis Release)
### Released
- 🚀 **核心功能上线**:
  - A股实时行情监控 (SINA/EM API)。
  - 只能 Volume Profile (筹码分布) 策略分析。
  - 基础 Streamlit 可视化大屏。
