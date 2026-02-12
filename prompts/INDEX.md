# Prompts Index

This file maps prompt filenames to config keys used in the code.

## System Prompts (角色设定)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_system.md` | `proposer_system` | 蓝军主帅系统设定 |
| `reviewer_system.md` | `reviewer_system` | 红军风控系统设定 |
| `blue_quant_sys.md` | `blue_quant_sys` | 数学官设定 |
| `blue_intel_sys.md` | `blue_intel_sys` | 情报官设定 |
| `red_quant_sys.md` | `red_quant_auditor_system` | 数据审计官 |
| `red_intel_sys.md` | `red_intel_auditor_system` | 情报审计官 |

## User Prompts (用户提示词模板)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_base.md` | `proposer_base` | 基础持仓/规则模板 |
| `proposer_premarket_suffix.md` | `proposer_premarket_suffix` | 盘前规划附录 |
| `proposer_intraday_suffix.md` | `proposer_intraday_suffix` | 盘中 realtime 附录 |
| `proposer_noon_suffix.md` | `proposer_noon_suffix` | 午间复盘附录 |
| `proposer_simple_suffix.md` | `proposer_simple_suffix` | 简化分析模式 |
| `proposer_extreme_scenarios.md` | `proposer_extreme_scenarios` | 极端场景应对手册 |

## Audit Prompts (审计相关)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `reviewer_audit.md` | `reviewer_audit` | 初审模板 |
| `reviewer_noon_audit.md` | `reviewer_noon_audit` | 午间审计模板 |
| `reviewer_final_audit.md` | `reviewer_final_audit` | 终审模板 |
| `refinement_instruction.md` | `refinement_instruction` | 反思优化指令 |

## Final Prompts (最终决策)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_final_decision.md` | `proposer_final_decision` | 最终执行令模板 |

## 备份与兼容性笔记
- 规范化后的键名已在 v3.0.1 中作为单一事实源确立。
- 代码中的旧引用已批量迁移。
