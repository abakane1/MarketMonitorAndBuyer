# Changelog

## [4.1.0] - 2026-03-14 (Week 1 & 2 完成)

> 📍 开发路线图: `docs/v4.1_ROADMAP.md`  
> 📊 项目状态: `docs/v4.1_STATUS.md`

### 🎯 Overview
v4.1 Week 1 & 2 完成，底层加固和AI功能模块全部上线。

---

### ✅ Week 2 已完成 (AI重装上阵)

#### 1. 🧠 LLM智能关联 (Intelligence Hub 2.0 Phase 2)
- **新增脚本**: `scripts/intel_analyzer.py`
  - 调用DeepSeek API自动分析情报内容
  - 智能关联ETF代码和置信度(50%+)
  - 判断利好/利空/中性情感
  - 保存到 `intelligence_stocks` 关联表
- **测试示例**:
  ```
  输入: "中芯国际业绩超预期，芯片板块利好"
  输出:
    • 588200: 置信度95%, 情感bullish
    • 588750: 置信度95%, 情感bullish
    • 588710: 置信度70%, 情感bullish
  ```

#### 2. 📦 自动归档系统 (Intelligence Hub 2.0 Phase 3)
- **新增脚本**: `scripts/intel_archive.py`
  - 归档6个月前的历史情报
  - LLM自动压缩摘要(100字以内)
  - 清理过期数据，节省存储
- **命令**: `python scripts/intel_archive.py --dry-run`

#### 3. 💾 本地缓存降级 (Data Fallback Protocol Phase 2)
- **新增脚本**: `scripts/market_snapshot.py`
  - 每日收盘后保存自选股快照
  - 极端网络中断时提供静态查询
  - 支持历史快照管理

#### 4. ⚔️ 双专家风控矩阵 (Dual-Expert Phase 1)
- **新增模块**: `capability_platform/risk/dual_expert_decision.py`
  - 红蓝决策矩阵编码实现
  - 风险评分>7分自动拦截交易
  - 可配置风控阈值
- **决策规则**:
  ```
  Blue买入 + Red<4分  → ✅ 强力买入
  Blue买入 + Red 4-7分 → ⚠️ 谨慎买入
  Blue买入 + Red>7分  → 🛑 拒绝买入
  ```

### 📁 Week 2 新增文件
```
scripts/
├── intel_analyzer.py           # LLM智能分析
├── intel_archive.py            # 自动归档系统
└── market_snapshot.py          # 市场离线快照

capability_platform/risk/
└── dual_expert_decision.py     # 双专家决策引擎
```

---

### ✅ Week 1 已完成 (底层加固)

#### 1. 🗄️ 数据库结构升级 (Intelligence Hub 2.0 Phase 1)
- **新增字段**:
  - `is_archived` - 归档标记
  - `summary` - 压缩摘要
  - `confidence` - 置信度
  - `sentiment` - 情感标签 (bullish/bearish/neutral)
- **新增表**:
  - `intelligence_stocks` - 情报-ETF多对多关联表
  - `etf_keywords` - ETF关键词配置表
- **默认ETF配置**: 588200, 588710, 588750 已预置
- **索引优化**: 新增4个复合索引加速查询

#### 2. 🛡️ 数据源健康监控 (Data Fallback Protocol Phase 1)
- **新增模块**: `utils/data_health_monitor.py`
  - 自动检测 Sina/Tencent/AKShare 数据源健康状态
  - 记录成功率、响应时间、连续失败次数
  - 智能推荐最佳数据源
- **新增脚本**: `scripts/monitor_data_health.py`
  - 命令行健康检查工具
  - 异常时自动告警
- **健康日志**: `logs/data_health.json`

#### 3. 🔧 Bug修复
- **昨日收盘价错误**: `get_stock_realtime_info()` 现在优先从日线历史获取真实昨收

### 📁 Week 1 新增文件
```
migration_tool/
└── migrate_v4.1_intelligence.sql   # 数据库迁移脚本

utils/
└── data_health_monitor.py          # 数据源健康监控

scripts/
└── monitor_data_health.py          # 健康检查命令行工具
```

---

## [4.1.0] - 2026-03-14 (v4.1 全部完成)

> 📍 开发路线图: `docs/v4.1_ROADMAP.md`  
> 📊 项目状态: `docs/v4.1_STATUS.md`

### 🎯 Overview
**v4.1 全部开发完成！** Week 1/2/3 所有功能模块已上线。

### ✅ Week 3 已完成 (体验与风控)

#### 1. 📊 ETF专属情报页面 (Intelligence Hub 2.0 Phase 4)
- **新增组件**: `components/intel_timeline.py`
  - ETF专属情报展示页面
  - 情报时间轴可视化
  - 情感标签可视化 (🟢利好/🔴利空/⚪中性)
  - 支持按时间、情感筛选
- **功能特性**:
  - 实时行情联动
  - 已归档情报摘要展示
  - 响应式UI设计

#### 2. 🔌 AI接口统一 (Dual-Expert Phase 2)
- **新增模块**: `utils/ai_interface.py`
  - 统一Web界面和命令行的AI调用
  - 消除skill与人工操作差异
  - 提供一致的API调用体验
- **便捷封装**:
  - `StrategyGenerator` - 策略生成
  - `RiskAuditor` - 风险审计
  - `UnifiedAIInterface` - 统一调用

#### 3. 📈 批量风控分析 (Dual-Expert Phase 2)
- **新增脚本**: `scripts/batch_risk_audit.py`
  - 批量对多个标的进行红蓝双专家分析
  - 输出结构化风控报告 (text/json/md)
  - 支持自选股列表批量分析
- **使用示例**:
  ```bash
  python scripts/batch_risk_audit.py 588200 588710 --format md
  python scripts/batch_risk_audit.py --watchlist --format json
  ```

### 📁 Week 3 新增文件
```
components/
├── intel_timeline.py           # ETF情报时间轴

utils/
└── ai_interface.py             # 统一AI接口

scripts/
└── batch_risk_audit.py         # 批量风控分析
```

### 🎉 v4.1 完整功能清单

| 模块 | 功能 | 状态 |
|------|------|------|
| **数据库升级** | 冷热分离、关联表、ETF配置 | ✅ Week 1 |
| **健康监控** | Sina/Tencent可用性检测 | ✅ Week 1 |
| **LLM智能关联** | DeepSeek自动分析→ETF关联 | ✅ Week 2 |
| **自动归档** | 6个月前情报压缩归档 | ✅ Week 2 |
| **离线快照** | 极端网络中断静态查询 | ✅ Week 2 |
| **双专家风控** | 风险>7分自动拦截 | ✅ Week 2 |
| **ETF情报页** | 专属情报时间轴UI | ✅ Week 3 |
| **AI接口统一** | Web与命令行一致 | ✅ Week 3 |
| **批量风控** | 多标的同时分析 | ✅ Week 3 |

---

## [4.2.0] - 2026-03-14 (回测框架 + 绩效归因 + v4.1优化)

> 📍 开发路线图: `docs/v4.2_ROADMAP.md`

### 🎯 Overview
v4.2 核心功能开发完成！包含回测框架、绩效归因分析、v4.1集成测试。

### ✅ v4.2 核心功能

#### 1. 🔄 回测框架建设 (P0)
- **回测引擎** (`capability_platform/backtest/engine.py`)
  - 分钟级/日级行情回测
  - 策略执行模拟
  - 交易记录生成
  - 权益曲线追踪
  
- **绩效指标** (`capability_platform/backtest/metrics.py`)
  - 收益类: 累计收益率、年化收益率、超额收益
  - 风险类: 最大回撤、波动率、夏普比率、卡玛比率
  - 交易类: 胜率、盈亏比、平均持仓周期
  
- **交易模拟器** (`capability_platform/backtest/simulator.py`)
  - 滑点模拟 (高斯分布)
  - 手续费计算
  - 部分成交模拟
  - 市场冲击模型

- **回测入口** (`scripts/backtest_framework.py`)
  - 标准化回测流程
  - 人机交易对比
  - 多格式报告输出

#### 2. 📊 绩效归因分析 (P1)
- **Brinson归因** (`capability_platform/analytics/brinson_attribution.py`)
  - 资产配置收益 (Allocation Effect)
  - 个股选择收益 (Selection Effect)
  - 交互收益 (Interaction Effect)
  - 行业贡献分解

- **归因入口** (`scripts/performance_attribution.py`)
  - 组合 vs 基准对比
  - 多格式报告 (text/json/md)

#### 3. 🧪 v4.1集成测试 (优化)
- **集成测试** (`tests/integration/test_v4.1_features.py`)
  - 数据库结构验证 (14/15通过)
  - 模块协同测试
  - 双专家决策矩阵验证

### 📁 v4.2新增文件
```
capability_platform/
├── backtest/
│   ├── __init__.py
│   ├── engine.py              # 回测引擎
│   ├── metrics.py             # 绩效指标
│   └── simulator.py           # 交易模拟器
├── analytics/
│   └── brinson_attribution.py # Brinson归因

scripts/
├── backtest_framework.py      # 回测入口
└── performance_attribution.py # 归因分析

tests/integration/
└── test_v4.1_features.py      # v4.1集成测试
```

### 🚀 快速开始
```bash
# 回测测试
python capability_platform/backtest/engine.py

# 归因分析测试
python scripts/performance_attribution.py

# 集成测试
python tests/integration/test_v4.1_features.py

# 运行回测
python scripts/backtest_framework.py 588200 --start 2024-01-01 --end 2024-03-01
```

---

## [4.1.x] - 2026-03 (v4.1中版本开发中)

> 📍 开发路线图: `docs/v4.1_ROADMAP.md`

### 🎯 Overview
推进v4.1中版本三大核心模块开发，解决情报系统膨胀、数据源不稳定、风控拦截系统化问题。

### 🏗️ 三大核心模块开发计划

#### 1. 🧠 投研情报系统涅槃重构 (Intelligence Hub 2.0)
- ✅ **Phase 1**: 数据库结构升级 (已完成)
- 🔄 **Phase 2**: LLM深度语义关联 (Week 2)
- 🔄 **Phase 3**: 自动归档系统 (Week 2)
- 🔄 **Phase 4**: ETF专属页 (Week 3)

#### 2. 🛡️ 数据基石与底层容灾网 (Data Fallback Protocol)
- ✅ **Phase 1**: 多源调度器 + 健康监控 (已完成)
- 🔄 **Phase 2**: 本地缓存降级策略 (Week 2)

#### 3. ⚔️ 双子星智能阵列演进 (Dual-Expert Architecture)
- 🔄 **Phase 1**: 红蓝决策矩阵上链 (Week 2)
- 🔄 **Phase 2**: AI接口统一 (Week 3)

### 📅 剩余开发阶段
- **Week 2**: Phase 2 - AI重装上阵 (智能关联 + 自动归档)
- **Week 3**: Phase 3 - 体验与风控 (专属页 + 风控拦截)
- **Week 4**: 集成测试与文档更新

### 📁 规划中模块
```
scripts/intel_archive.py          # 情报自动归档
scripts/intel_analyzer.py         # LLM智能分析
scripts/market_snapshot.py        # 市场离线快照
components/intel_timeline.py      # 情报时间轴组件
capability_platform/risk/dual_expert_decision.py  # 双专家决策
```

---


All notable changes to the **MarketMonitorAndBuyer** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.0] - 2026-03-12 (Research Report Refactor)

### 🎯 Overview
重构历史研报记录功能，解决数据存储混乱、界面展示不清晰的问题。现在每一步都清晰存储和展示自己的提示词、思考过程和决策内容。

### ✨ Features (新特性)
- **结构化数据模型** (`utils/research_report.py`)
  - `ResearchReport`: 研报记录主类
  - `StepRecord`: 单步记录 (存储每一步的 system_prompt, user_prompt, reasoning, content)
  - `FinalDecision`: 最终决策摘要
  - 自动从旧格式迁移 (`from_legacy_log`)

- **全新展示组件** (`components/research_history.py`)
  - 📊 策略与执行追踪表格
  - 📑 三种展示模式:
    - **分步详情**: 每一步独立展示 (决策内容 | 思考过程 | 提示词)
    - **全流程对比**: 横向对比各步骤决策变化
    - **原始数据**: 兼容旧数据显示
  - 🎨 美观的步骤卡片设计，带颜色区分蓝军/红军
  - 📈 决策摘要自动提取 (方向/价格/股数/止损/止盈)

### 🔧 Improvements (改进)
- **存储逻辑优化**:
  - 新增 `save_structured_research_report()`: 保存结构化数据
  - 新增 `load_structured_research_reports()`: 加载结构化数据
  - 保留向后兼容，旧数据仍可正常显示

- **数据清晰分离**:
  - Step 1 (蓝军初稿): 独立存储 system_prompt + user_prompt + reasoning + content
  - Step 2 (红军初审): 独立存储提示词和审计结果
  - Step 3 (蓝军优化): 独立存储优化逻辑和反思过程
  - Step 4 (红军终审): 独立存储终审意见
  - Step 5 (最终执行): 独立存储最终决策

### 🐛 Bug Fixes
- 修复了全流程详情中提示词和决策内容混在一起的问题
- 修复了定稿中包含其他步骤决策记录的混乱显示
- 修复了思考过程无法按步骤查看的问题

### 📁 New Modules
```
utils/
└── research_report.py       # 研报数据模型 (ResearchReport, StepRecord, FinalDecision)

components/
└── research_history.py      # 历史研报展示组件
```

### 🔄 Migration (迁移说明)
- 旧数据自动兼容，通过 `from_legacy_log()` 方法转换
- 新保存的数据使用 v2.1 格式，包含完整的结构化信息
- 无需手动干预，系统会自动处理新旧数据混存

## [4.0.0] - 2026-03-09 (Architecture Refactor: Data & Capability Platform)

### 🏗️ Architecture Upgrade (架构升级)
- **数据中台 (Data Platform)**: 统一数据管理层，解决数据不一致问题
  - `data_platform/models/`: 统一数据模型 (PositionModel, TradeModel, QuoteModel)
  - `data_platform/services/`: 统一数据服务 (PositionService, TradeService, QuoteService)
  - 实现单一事实来源 (Single Source of Truth)
  - 所有数据操作必须通过 Service 层

- **能力中台 (Capability Platform)**: 统一算法和业务逻辑层
  - `capability_platform/calculators/`: 统一计算引擎
    - `PositionCalculator`: 持仓计算（加权平均成本法、摊薄成本法）
    - `PnLCalculator`: 盈亏计算（浮动盈亏、今日盈亏、已实现盈亏）
    - `FeeCalculator`: 费率计算（ETF/股票区分）
  - `capability_platform/risk/`: 风控引擎
    - `TradeLimit`: 交易频率限制（每日3笔、24小时冷静期）
    - `PositionLimit`: 持仓限制检查

### ✨ Features (新特性)
- 数据模型不可变设计 (frozen dataclass)，确保数据一致性
- 统一缓存管理，避免重复计算
- 持仓重新计算功能，解决历史数据不一致问题
- 完整的交易执行流程（校验→计费→执行→更新持仓）

### 📁 New Modules (新增模块)
```
data_platform/
├── models/
│   ├── base.py           # 基础模型和枚举
│   ├── position.py       # 持仓模型
│   ├── trade.py          # 交易模型
│   └── quote.py          # 行情模型
└── services/
    ├── base_service.py   # 基础服务类
    ├── position_service.py
    ├── trade_service.py
    └── quote_service.py

capability_platform/
├── calculators/
│   ├── position_calculator.py
│   ├── pnl_calculator.py
│   └── fee_calculator.py
└── risk/
    ├── trade_limit.py
    └── position_limit.py
```

### 🔧 Refactoring (重构)
- 所有费率计算统一到 `FeeCalculator`
- 所有持仓计算统一到 `PositionCalculator`
- 所有盈亏计算统一到 `PnLCalculator`
- 所有交易限制统一到 `TradeLimit`

### 📖 Documentation (文档)
- 新增 `ARCHITECTURE_v4.md` 架构设计文档
- 详细的目录结构和接口契约说明
- 数据一致性检查清单

## [3.2.0] - 2026-02-28 (Prompt Refactor: Hardcoded Prompts Migration + UI Rebuild)

### Added (新增)
- **提示词统一管理中心化 (Unified Prompt Management)**:
  - 创建 `prompts/defaults/` 目录，存放默认 fallback 提示词
  - 新增 6 个 Markdown 格式提示词文件：
    - `agents/red_commander_system.md` - 红军最高指挥官设定
    - `agents/intelligence_processor_system.md` - 金融情报分析师设定
    - `agents/qwen_agent_system.md` - 金融情报搜集员设定
    - `defaults/fallback_quant_sys.md` - 量化分析引擎默认提示词
    - `defaults/fallback_intel_sys.md` - 市场情报分析师默认提示词
    - `defaults/fallback_red_quant_sys.md` - 风险审计官默认提示词
    - `defaults/fallback_red_intel_sys.md` - 合规审查官默认提示词
  - 更新 `utils/prompt_loader.py` 的 `PROMPT_MAPPINGS`，支持新的提示词键名

### Changed (变更)
- **硬编码提示词迁移 (Hardcoded Prompts Migration)**:
  - `utils/legion_advisor.py`: 迁移蓝军/红军子 Agent 的硬编码系统提示词
  - `utils/ai_advisor.py`: 迁移审计、反思、最终决策的默认提示词
  - `utils/intelligence_processor.py`: 迁移情报分析的硬编码系统提示词
  - `utils/qwen_agent.py`: 迁移 Qwen 搜索 Agent 的硬编码系统提示词
- **代码逻辑优化**: 所有提示词优先从 `prompt_templates` 加载，无配置时回退到 Markdown 文件，最后才是代码内硬编码
- **提示词中心界面重构 (Prompt Center UI Rebuild)**:
  - 按照实际使用场景重新设计 6 个分类 Tab：策略生成、风控审计、军团智能体、交易原则、工具与情报、模型配置
  - 每个提示词显示详细的用途说明 (`desc`)、代码调用位置 (`usage`)、分类标签 (`category`)
  - 新增提示词统计概览：已加载数、已分类数、未分类数、分类覆盖率
  - 未分类提示词检测和展示，便于维护
  - 更新 `prompts/INDEX.md` 文档，添加架构图和详细分类说明

### Fixed (修复)
- **提示词可维护性**: 解决分散在各处的硬编码提示词难以统一管理和版本控制的问题
- **提示词热更新**: 现在修改 `prompts/` 目录下的 Markdown 文件即可生效，无需重启应用

---

## [3.1.0] - 2026-02-12 (Stock Selector Refactor & Global Refresh)
### Added (新增)
- **全局一键刷新 (Global Refresh)**:
  - 侧边栏新增“🔄 一键刷新实时数据”按钮，支持一次性同步全市场快照并循环更新所有关注股票的分钟线。
- **New Stock Selector (新版股票选择器)**:
  - 重构侧边栏，移除全市场下拉框，改为 **代码输入 + 自动验证** 模式。
  - 支持 **Sina/Tencent API** 自动获取股票/ETF 名称。
  - 移除了 5 只关注上限，支持无限添加自选股。
  - 关注列表新增 **❌ 移除按钮**。

### Fixed (修复)
- **ETF Compatibility**: 修复了 5 开头 (如 563, 510) 的 ETF 无法被 Sina API 正确识别名称的问题。
- **Scope Error**: 修复了 `data_fetcher.py` 中 `STOCK_SPOT_PATH` 变量作用域报错 (`UnboundLocalError`)。

### Changed (变更)
- **UI Streamlining**: 移除了仪表盘中每个股票单独的刷新按钮，保持界面整洁。
- **Project Structure**: 清理了临时测试脚本，规范了 Prompt 文件结构。

---

## [2.8.0] - 2026-02-10 (Prompt Refactor & Data Source Resilience)
### Added (新增)
- **提示词 Markdown 化 (Prompt Refactoring)**:
  - 创建 `prompts/` 目录结构，将分散在代码中的提示词迁移为 11 个 Markdown 文件
  - 新增 `utils/prompt_loader.py` 模块，支持从文件加载提示词
  - 保留向后兼容，支持键名别名映射
- **备用数据源 (Fallback Data Sources)**:
  - 新增 `utils/data_fallback.py`，集成新浪财经和腾讯财经 API
  - 修改 `utils/data_fetcher.py`，当东方财富(akshare)被封时自动切换备用源
  - 数据获取优先级：本地缓存 → 新浪财经 → 腾讯财经 → 历史数据

### Changed (变更)
- **配置加载优化**: `utils/config.py` 现在优先从 Markdown 文件加载提示词，失败时回退到加密 JSON
- **资金流向数据增强**: `get_stock_fund_flow()` 现在使用新浪财经实时数据更新价格和涨跌幅，避免显示过期缓存数据

### Fixed (修复)
- **东方财富封锁应对**: 解决 akshare 因东方财富反爬虫策略导致的数据获取失败问题
- **资金流向数据不一致**: 修复资金流向显示的涨跌幅与实时行情不符的问题（因使用缓存的历史数据）
- **本地缓存过期**: 新增备用数据源后，当本地缓存过期时自动从新浪财经/腾讯财经获取最新数据

---

## [2.7.1] - 2026-02-09 (System Maintenance & Environment Hardening)
### Added (新增)
- **环境自修复支持**: 针对 macOS 环境优化了 `start_mac.sh` 的鲁棒性，支持 Python 3.12+ 的虚拟环境自动重建与依赖安装。
- **数据源稳定性维护**: 对 `utils/data_fetcher.py` 进行了维护，确保持仓监控与行情抓取的稳定性（适配 efinance 等数据源）。

### Fixed (修复)
- **Version Parity**: 统一了 UI (`main.py`)、`VERSION` 文件与文档之间的版本号显示，修复了长期存在的硬编码版本滞后问题。
- **Cleanup**: 移除了冗余的调试脚本与历史模拟日志。

---

## [2.7.0] - 2026-02-02 (Structural Integrity & Intelligence Boost)
### Added (新增)
- **结构化策略持久化 (Structural Persistence)**:
  - **Database Upgrade**: 为 `strategy_logs` 增加了 `details` JSON 字段，解决了历史记录中初稿丢失和内容重复的顽疾。
  - **Full Traceability**: 全流程日志现在能够完美还原“草案-初审-反思-终审-执行”的所有 Prompt 和回答。
- **情报库实时资讯 (Real-time Intel)**:
  - **News Integration**: 集成东方财富实时个股新闻源，支持一键刷新。
  - **AI Summarization**: 新增“AI 提炼入库”功能。调用 DeepSeek 对最新新闻进行去噪摘要，提炼出利好/利空核心情报并存入数据库。
- **UI/UX 鲁棒性**:
  - 全流程详情由“字符串切割”升级为“结构化 JSON 解析”，大幅提升了显示稳定性。
  - 修复了情报去重界面在多组重复时的 Streamlit Key 冲突报错。

### Changed (变更)
- **专家系统纯化 (Model Rationalization)**:
  - **DeepSeek Solo**: 根据用户要求“卸载”了 Qwen 专家。现在的蓝军（主帅）和红军（审计）均默认且强制使用 DeepSeek R1，确保策略逻辑的高度严谨。
  - **Negative Constraints**: 强化了盘后模式下的 Prompt 负面约束，严禁 AI 生成无效的日内操作建议。

### Fixed (修复)
- **Label Correction**: 自动修复了盘后预判时“今日交易边界”标签的误导，自动修正为“下个交易日预计”。
- **Expert API**: 重构了 `BaseExpert` 接口及其子类，修复了后续审计轮次日志为空的架构缺陷。

---

## [2.6.0] - 2026-01-29 (3-Way Battle Strategy Lab)
### Added (新增)
- **Strategy Lab 3-Way Battle (三方博弈)**:
  - **3-Way Simulation**: 在“人机对弈”复盘中引入 **Qwen Legion** (Qwen 军团) 作为第三方玩家，与 **DeepSeek** 和 **User (实盘)** 同台竞技。
  - **Multi-Model Backtesting**: 策略回溯支持指定模型 (DeepSeek / Qwen)，并分别记录日志。
  - **Visualization**: 收益曲线和战绩结算全面升级，支持三方数据对比。
- **Database Schema Upgrade**:
  - `strategy_logs` 表自动迁移添加 `model` 字段，用于区分策略来源。

## [2.5.1] - 2026-01-29 (Config Optimization)
### Changed (变更)
- **Prompts Storage Split**: 将 `prompts` 从 `user_config.json` 分离到独立的 `prompts_encrypted.json`，优化配置文件结构，减小文件体积。
- `user_config.json` 现在只保留 `settings`，更加清晰。
- 保持对旧格式的向后兼容。

---

## [2.5.0] - 2026-01-29 (Blue Legion / MoE)
### Added (新增)
- **Blue Legion Architecture (蓝军军团 MoE)**:
  - 蓝军不再是单兵作战，而是升级为【混合专家模型 (Mixture of Experts)】系统。
  - **数学官 (Quant Agent)** (Qwen-Plus): 专攻资金流向、分时盘口、盈亏比计算。
  - **情报官 (Intel Agent)** (Qwen-Plus): 专攻新闻叙事、历史战绩回溯、预期差分析。
  - **蓝军主帅 (Commander)** (Qwen-Max): 综合专家报告，依据 GTO 策略制定最终作战计划。
- **Auto-Drive Step 1 Upgrade**: 极速模式下 Step 1 自动触发军团联合作战。
- **Configuration**:
  - 默认蓝军升级为 **Qwen-Max** (Commander)。
  - 默认红军升级为 **DeepSeek** (Risk Auditor)。
  
### Fixed (修复)
- **Auto-Drive Step 5 Empty Data**: 修复了最终定稿数据无法显示的问题 (更新了 `deepseek_final_decision` 模版以强制输出标准格式)。
- **Post-Market Date Logic**: 修复了盘后复盘时 AI 仍按“今日”制定计划的逻辑错误 (自动判定并指向下一个交易日)。

## [2.2.0] - 2026-01-29 (Closed Loop System)
### Added (新增)
- **Step 5: 最终执行令 (Final Execution Order)**:
  - 核心流程升级为完整的 5 步闭环：蓝军草案 (v1) -> 红军初审 -> 蓝军优化 (v2) -> 红军终审 -> **蓝军定稿 (Execution)**。
  - 最后一步重归蓝军主帅，由其阅读终审裁决书，签署极简的执行指令 (买/卖/放弃)，确保决策权的回归。
- **全模式支持**: Step 5 同时支持 **极速模式 (Auto-Drive)** 和 **手动分步模式**。
- **UI 体验**:
  - 策略结果全线升级为 5 页签视图，默认置顶显示最新的“定稿”指令。
  - 优化了即时渲染逻辑，修复了旧版视图中页签缺失的问题。

## [2.1.0] - 2026-01-28 (Full Process Visibility)
### Added (新增)
- **全链路溯源 (Full Process Traceability)**: 策略入库时，现在记录完整的 4 阶段提示词历史 (Mega Log)，包括 Draft / Audit 1 / Refinement / Final Verdict 的所有 System & User Prompts。
- **Auto-Drive 逻辑完善**: 修复了极速模式下“终极裁决”状态未正确传递导致手动按钮残留的问题，确保自动流程的一致性。

## [2.0.0] - 2026-01-28 (Final Architecture Upgrade)
### Added (新增)
- **双轮闭环 (2-Round Audit Loop)**: 实现了完整的 AI 迭代闭环：蓝军草案 (v1) -> 红军初审 -> 蓝军反思 (v2) -> 红军终审 (Final Verdict)。
- **极速模式 (Auto-Drive Mode)**: 全新功能，支持一键自动化执行上述 4 阶段流程，包含完整的中间状态记录。
- **蓝军自主权 (Blue Team Autonomy)**: 在优化阶段引入独立判断逻辑，蓝军不再盲从红军，而是有权反驳幻觉或接受合理建议。
- **手动终审 (Manual Final Verdict)**: 为手动模式增加了第 4 阶段（终审环节），补全了交互链路。

### Changed (优化)
- **红军人设重塑**: 从“保守风控官”升级为“LAG + GTO 专家”，与蓝军同一体系下的 Peer Review。
- **红军升级 (Red Team Upgrade)**: 审计模型由 `qwen-plus` 升级为阿里巴巴最强模型 `qwen-max`，进一步提升逻辑审查能力。
- **状态机重构**: 全面重构 `strategy_section.py` 的状态管理，支持多阶段 (Draft -> Refined -> Final) 的平滑切换。

## [1.9.0] - 2026-01-28 (Session Review Upgrade)
### Added (新增)
- **分时复盘引擎 (Segmented Session Review)**:
  - **午间复盘 (Noon Review)**: 智能识别午间休盘时段 (11:30-13:00)。提供上午走势总结与下午开盘预判，侧重于“持仓风险控制”与“日内反转博弈”。
  - **全天复盘 (Daily Review)**: 盘后 (15:00+) 自动切换为全天复盘模式，侧重于“隔日计划”与“波段趋势”。
  - **动态 UI**: 策略生成按钮根据当前时间自动跟随变色与更名，减少用户误操作。

### Changed (优化)
- **提示词架构**: 新增 `deepseek_noon_suffix` 专用模板，针对午间场景做了 Token 剪裁与逻辑优化。
- **时间感知**: 引入 `get_market_session` 统一管理交易时段状态。

## [1.8.1] - 2026-01-28 (Prompt Optimization & Calc Fixes)
### Added (新增)
- **AI 智能提示词优化 (Prompt Optimization)**:
  - 提示词中心新增 **AI 智能优化** 功能。利用 DeepSeek R1 的推理能力，一键重构、清洗并去重所有系统 Prompt。
  - **Diff 可视化**: 提供优化前后的代码比对视图 (Diff View)，支持用户确认后一键写入配置。

### Fixed (修复)
- **累计盈亏计算修正**: 
  - 修复了 **Holdings Override (持仓修正)** 操作未重置成本流水的 Bug。现在系统会将修正操作视为一次“重置基准”，确保后续累计盈亏计算准确。
- **AI 决策数据校准**:
  - 修复了 AI 决策上下文缺失 `available_cash` (可用资金) 和字段名不匹配的问题，消除了【最终决策关键数据】中的显示错误。

## [1.8.0] - 2026-01-27 (Market Review & Prediction Transformation)
### Changed (系统转型)
- **定位重构**: 系统从“实时盯盘”正式转型为 **“复盘与预判辅助系统”**。
  - **盘中策略移除**: 彻底移除了“算法实时监控”与“盘中对策”功能，避免交易干扰。
  - **AI 角色升级**: AI 助手重新命名为“复盘助手”，专注于收盘后的复盘总结与明日预判。
- **资金限额动态化**: 
  - 引入 **有效限额 (Effective Limit)** 概念，计算公式升级为 `基础限额 + 累计盈亏`。
  - 实现了利润自动复投机制：当股票盈利时，算法自动允许使用盈利部分扩充持仓。

### Added (新增)
- **交易补录 (Backdating)**:
  - 交易记账面板新增 **“补录历史交易”** 选项，支持用户指定日期和时间插入历史买卖记录。
- **摊薄成本法 (Verified Cost Basis)**:
  - 重构了卖出逻辑：卖出获利时自动降低剩余持仓成本，卖出亏损时增加持仓成本。相比旧版的“移动加权平均”，该逻辑更能反映真实持仓心理压力。

### Fixed (修复)
- **配置防丢机制 (Config Hardening)**: 
  - 重写了 `load_config` 逻辑，在读取不到配置文件时 **强制报错停止**，不再自动回退到默认空配置。彻底修复了 API Key 意外丢失的顽疾。
- **数据库一致性**:
  - 移除了持仓查询的缓存机制，修复了快速连续交易（如连续补录）时数据更新不及时的问题。

## [1.7.0] - 2026-01-25 (Interactive Backtest & Evolution)
### Added (新增)
- **动态回测实验室 (Dynamic Strategy Lab)**:
  - **可视化重构**: 策略回测不再展示静态结果，而是支持逐分钟回放交易日（股价、资产、信号实时跳动）。
  - **多维曲线对比**: 动态绘制 "AI 收益率" vs "实盘收益率" vs "标的涨跌幅" 三条曲线，直观呈现 Alpha 来源。
  - **人机对弈 (Human vs AI)**: 系统自动识别用户实盘优于 AI 的时刻，并提供 "Extract Alpha" 功能。
- **指令自进化闭环 (Prompt Evolution)**:
  - **Alpha 提取**: 当用户战胜 AI 时，调用 DeepSeek 分析用户操作的优越性（如捕捉盘口流动性、早盘抢跑）。
  - **一键更新**: 自动生成 System Prompt 的优化建议，支持 diff 预览、编辑并一键写入配置文件，无需手动复制粘贴。
- **交易日历风控 (Trading Calendar)**:
  - 内置 2026 年完整节假日表（含春节、国庆等）。
  - **严格日期逻辑**: 自动识别非交易日（周末/假期），所有盘后生成的策略自动顺延至“下一个交易日”，彻底修复了周五/节假日策略日期的显示错误。

### Fixed (修复)
- **回测数据校准**:
  - 修复了资产基数计算逻辑（改为：初始资金 + 持仓市值），解决了收益率虚高的问题。
  - 支持识别数据库中的 `override` (持仓修正) 记录，确保回测状态与实盘完全同步。
- **AI 策略连续性**: 修复了回测时忽略“前一日盘前策略”的 Bug，现在系统会自动回溯读取前一晚生成的作战计划。

## [1.6.1] - 2026-01-23 (Stability & Fixes)
### Fixed (修复)
- **情报系统恢复**: 彻底修复了 `intel_manager.py` 在重构过程中丢失的 `add_claims` 和 `get_claims_for_prompt` 函数。
- **数据迁移验证**: 修正了迁移脚本对策略日志路径的识别逻辑，成功从旧版文件找回 11 条研报记录并入库。
- **代码结构优化**: 统一了 `utils` 层对数据库的访问模式，解决了在高频刷新下的数据结构竞争问题。

## [1.6.0] - 2026-01-23 (Architecture & Persistence Upgrade)
### Architecture (架构升级)
- **全数据数据库化 (All-in-DB)**: 
  - 彻底完成了从 JSON 文件存储向 **SQLite** 数据库的架构迁移。
  - **核心配置分离**: `user_config.json` 现仅存储 API Key、系统设置与加密提示词 (Prompts)。
  - **业务数据迁移**: 关注列表、资金限额、情报数据、策略日志均已迁入 `user_data.db`。
- **数据一致性**: 
  - 持仓状态 (`shares`, `cost`, `base_shares`) 统一由数据库管理，彻底消除 JSON/DB 同步冲突。
  - 修复了数据迁移过程中的路径和格式兼容性问题，成功恢复历史研判记录。

### Fixed (修复与优化)
- **提示词严谨性修正**: 将所有提示词中的“**明天**”统一替换为“**下一个交易日 (Next Trading Day)**”，修复了周五/节假日前夕的 AI 幻觉问题。
- **系统健壮性**: 引入了更完善的数据库访问层 (`utils/database.py`)，支持列表/字典双模数据解析。

## [1.5.6] - 2026-01-23 (Core IP Security)
### Security (安全)
- **提示词加密存储 (Prompt Encryption)**:
  - 为了保护核心策略资产，系统引入了 **Fernet (AES-128)** 加密机制。
  - 所有存储在 `user_config.json` 中的 `prompts` 字段现在均以密文形式保存。
  - 加密密钥 `.secret.key` 自动生成并保存在根目录，只有持有此密钥的系统实例才能解密并使用 AI 策略。

## [1.5.5] - 2026-01-23 (ETF/Stock Strategy Differentiation)
### Added (新增)
- **ETF 专属策略逻辑**:
  - **智能识别**: 系统现在会自动根据代码前缀 (`51`/`15`/`58`) 识别标的是 ETF 还是个股。
  - **差异化人设**: 
    - **个股**: 维持 "LAG + GTO" 德州扑克博弈专家，侧重短线情绪与赔率。
    - **ETF**: 切换为 "**宏观趋势 + 网格交易专家**"，侧重长期走势、行业景气度与反脆弱配置，忽略个股黑天鹅噪音。

## [1.5.4] - 2026-01-23 (UI Config for Base Position)
### Added (新增)
- **底仓配置 UI (Base Config UI)**:
  - 在“资金配置 (Capital Allocation)”面板中新增了**“🔒 底仓锁定”**的交互式配置项。
  - 用户不再需要手动修改 JSON 配置文件，可直接在界面上调整“底仓股数”并一键保存，系统会自动激活风控护盾。

## [1.5.3] - 2026-01-23 (News Reasoning Upgrade)
### Changed (优化)
- **提示词思维链升级 (Prompt CoT Upgrade)**:
  - **消息面深度博弈**: 在 AI 思考路径中新增独立的 **"News Deep Dive"** 环节。
  - **二阶思维**: 强制要求 AI 对公告（如证监会问询回复、监管函）进行深度解读，不只是复述内容，更要预判“利空出尽”还是“新风险”，以及主力资金可能的洗盘/诱多手段。
  - **针对性优化**: 专为 600076 等处于敏感消息期的股票定制了分析逻辑。

## [1.5.2] - 2026-01-22 (Professional News Integration)
### Added (新增)
- **权威信源接入 (Professional News Source)**:
  - 针对秘塔搜索信息可能不够专业的问题，新增了 **EastMoney (东方财富)** 官方个股新闻源。
  - **自动注入**: 系统现会自动抓取并筛选最新的 Top 5 专业财经新闻/公告，直接注入到 AI 的研判上下文中，与秘塔搜索结果互补。

## [1.5.1] - 2026-01-22 (Base Position Logic)
### Added (新增)
- **底仓管理系统 (Base Position Strategy)**:
  - **核心逻辑**: 在 `user_config.json` 中为股票配置 `base_shares` (底仓)。系统自动将持仓划分为 **🔒 底仓 (Locked)** 和 **🔄 可交易 (Tradable)** 两部分。
  - **AI 风控**: 强制注入“底仓红线”到 Prompt，明确告知 AI 禁止触碰底仓，所有卖出建议的上限严格受限于“可交易筹码”。
  - **UI 护盾**: 在策略面板显著位置显示“风控护盾已激活”状态栏。

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
