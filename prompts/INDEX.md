# Prompts Index

This file maps prompt filenames to config keys used in the code.

## System Prompts (角色设定)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_system.md` | `proposer_system` | 蓝军主帅系统设定 |
| `reviewer_system.md` | `reviewer_system` | 红军风控系统设定 |
| `blue_quant_sys.md` | `blue_quant_sys` / `quant_agent_system` | 数学官设定 |
| `blue_intel_sys.md` | `blue_intel_sys` / `intel_agent_system` | 情报官设定 |
| `red_quant_sys.md` | `red_quant_auditor_system` | 数据审计官 |
| `red_intel_sys.md` | `red_intel_auditor_system` | 情报审计官 |

## User Prompts (用户提示词模板)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_base.md` | `proposer_base` | 基础持仓/规则模板 |
| `proposer_premarket_suffix.md` | `proposer_premarket_suffix` | 盘前规划附录 |
| `proposer_intraday_suffix.md` | `proposer_intraday_suffix` | 盘中实时附录 |
| `proposer_noon_suffix.md` | `proposer_noon_suffix` | 午间复盘附录 |
| `proposer_simple_suffix.md` | `proposer_simple_suffix` | 简化分析模式 |

## Audit Prompts (审计相关)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `reviewer_audit.md` | `reviewer_audit` | 初审模板 |
| `reviewer_final_audit.md` | `reviewer_final_audit` | 终审模板 |
| `refinement_instruction.md` | `refinement_instruction` | 反思优化指令 |

## Final Prompts (最终决策)

| Filename | Config Key | Usage |
|----------|-----------|-------|
| `proposer_final_decision.md` | `proposer_final_decision` | 最终执行令模板 |

## Legacy Mappings (兼容旧代码)

旧代码中使用的 key 名称也映射到这些文件：
- `deepseek_research_suffix` → `proposer_premarket_suffix`
- `qwen_system` → `reviewer_system`
- `qwen_audit` → `reviewer_audit`
