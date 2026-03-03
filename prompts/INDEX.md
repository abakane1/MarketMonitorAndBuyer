# Prompts Index v3.2.0

本文件映射提示词文件名到代码中使用的配置键名。

> **提示词中心重构说明 (v3.2.0)**: 提示词已按照实际使用场景重新分类，便于管理和维护。

---

## 🎯 策略生成 (Strategy Generation) - Blue Team

| 配置键名 | 文件名 | 用途 | 使用场景 |
|---------|--------|------|---------|
| `proposer_system` | `system/proposer_system.md` | 策略主帅系统设定 | DeepSeek/Kimi Commander |
| `proposer_base` | `user/proposer_base.md` | 策略基础模版 | 所有策略生成 |
| `proposer_premarket_suffix` | `user/proposer_premarket_suffix.md` | 盘前规划附录 | 盘前模式 |
| `proposer_intraday_suffix` | `user/proposer_intraday_suffix.md` | 盘中突发附录 | 盘中模式 |
| `proposer_noon_suffix` | `user/proposer_noon_suffix.md` | 午间复盘附录 | 午间模式 |
| `proposer_simple_suffix` | `user/proposer_simple_suffix.md` | 简易分析 | '简洁'分析深度 |
| `proposer_extreme_scenarios` | `user/proposer_extreme_scenarios.md` | 极端场景应对手册 | 极端行情 |
| `proposer_final_decision` | `final/proposer_final_decision.md` | 最终定稿指令 | 第五步：终极决策 |
| `refinement_instruction` | `audit/refinement_instruction.md` | 反思优化指令 | 第三步：反思优化 |

---

## 🛡️ 风控审计 (Risk Audit) - Red Team

| 配置键名 | 文件名 | 用途 | 使用场景 |
|---------|--------|------|---------|
| `reviewer_system` | `system/reviewer_system.md` | 风控官系统设定 | Red Team 审计 |
| `reviewer_audit` | `audit/reviewer_audit.md` | 初审模版 | 第二步：风险初审 |
| `reviewer_noon_audit` | `audit/reviewer_noon_audit.md` | 午间审计模版 | 午间审计 |
| `reviewer_final_audit` | `audit/reviewer_final_audit.md` | 终审模版 | 第四步：终极裁决 |

---

## ⚔️ 军团智能体 (Legion Agents) - MoE

| 配置键名 | 文件名 | 用途 | 使用场景 |
|---------|--------|------|---------|
| `blue_quant_sys` | `agents/blue_quant_sys.md` | 蓝军-数学官设定 | Blue Legion 子Agent |
| `blue_intel_sys` | `agents/blue_intel_sys.md` | 蓝军-情报官设定 | Blue Legion 子Agent |
| `red_quant_auditor_system` | `agents/red_quant_sys.md` | 红军-数据审计官 | Red Legion 子Agent |
| `red_intel_auditor_system` | `agents/red_intel_sys.md` | 红军-情报审计官 | Red Legion 子Agent |
| `red_commander_system` | `agents/red_commander_system.md` | 红军最高指挥官 | Red Legion 总指挥 |

---

## 📊 交易原则 (Trading Principles) - 双轨制

| 配置键名 | 文件名 | 用途 | 使用场景 |
|---------|--------|------|---------|
| `etf_position` | `principles/etf_position.md` | ETF仓位管理原则 | ETF标的 |
| `etf_risk` | `principles/etf_risk.md` | ETF风险控制原则 | ETF标的 |
| `stock_position` | `principles/stock_position.md` | 股票仓位管理原则 | 股票标的 |
| `stock_risk` | `principles/stock_risk.md` | 股票风险控制原则 | 股票标的 |
| `position_management` | `principles/position_management.md` | 仓位管理通用原则 | 所有标的 |
| `risk_management` | `principles/risk_management.md` | 风险管理通用原则 | 所有标的 |
| `market_microstructure` | `principles/market_microstructure.md` | 市场微观结构 | 分析参考 |

---

## 🔧 工具与情报 (Tools & Intelligence)

| 配置键名 | 文件名 | 用途 | 使用场景 |
|---------|--------|------|---------|
| `intelligence_processor_system` | `agents/intelligence_processor_system.md` | 金融情报分析师 | 新闻摘要分析 |
| `qwen_agent_system` | `agents/qwen_agent_system.md` | 金融情报搜集员 | 联网搜索情报 |

---

## 🔧 默认Fallback (Default Fallbacks)

当主提示词配置缺失时使用的默认提示词。

| 配置键名 | 文件名 | Fallback For |
|---------|--------|--------------|
| `fallback_quant_sys` | `defaults/fallback_quant_sys.md` | `blue_quant_sys` |
| `fallback_intel_sys` | `defaults/fallback_intel_sys.md` | `blue_intel_sys` |
| `fallback_red_quant_sys` | `defaults/fallback_red_quant_sys.md` | `red_quant_auditor_system` |
| `fallback_red_intel_sys` | `defaults/fallback_red_intel_sys.md` | `red_intel_auditor_system` |

---

## 🎛️ 模型专属覆盖 (Model Overrides)

特定模型的系统提示词增强，自动追加到基础系统提示词后。

| 配置键名 | 文件名 | 用途 |
|---------|--------|------|
| `deepseek_r1` | `model_overrides/deepseek_r1.md` | DeepSeek-R1 专属增强 |
| `kimi_k2_5` | `model_overrides/kimi_k2_5.md` | Kimi-K2.5 专属增强 |

---

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      提示词体系架构                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Strategy    │    │   Risk       │    │   Tools      │  │
│  │  Generation  │◄──►│   Audit      │    │              │  │
│  │  (Blue Team) │    │  (Red Team)  │    │ Intelligence │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                   │
│         ▼                                                   │
│  ┌────────────────────────────────────────────┐            │
│  │         Legion Agents (MoE)                 │            │
│  │  ┌──────────┐      ┌──────────────────┐    │            │
│  │  │  Quant   │      │  Red Quant       │    │            │
│  │  │  Agent   │      │  Auditor         │    │            │
│  │  └──────────┘      └──────────────────┘    │            │
│  │  ┌──────────┐      ┌──────────────────┐    │            │
│  │  │  Intel   │      │  Red Intel       │    │            │
│  │  │  Agent   │      │  Auditor         │    │            │
│  │  └──────────┘      └──────────────────┘    │            │
│  └────────────────────────────────────────────┘            │
│                                                             │
│  ┌────────────────────────────────────────────┐            │
│  │      Trading Principles (Dual-Track)        │            │
│  │         ETF Principles                     │            │
│  │         Stock Principles                   │            │
│  └────────────────────────────────────────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 变更日志

- **v3.3.0** (2026-02-28): 架构调整 - Kimi 成为蓝军主帅，DeepSeek 为红军审计官，Qwen 仅用于情报搜索
- **v3.2.0** (2026-02-28): 重构提示词分类，新增 Legion Agents 和 Trading Principles 分类
- **v3.0.1** (2026-02-10): 规范化提示词键名，建立单一事实源
- **v2.8.0** (2026-02-10): 初始 Markdown 化提示词系统
