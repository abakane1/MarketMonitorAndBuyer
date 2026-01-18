# Changelog

All notable changes to the **MarketMonitorAndBuyer** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
