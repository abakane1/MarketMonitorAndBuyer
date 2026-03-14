# 📚 MarketMonitorAndBuyer 文档中心

> 版本: v4.1.x  
> 最后更新: 2026-03-14

---

## 📂 文档结构

```
docs/
├── README.md                    # 本文档 - 文档导航
├── v4.1_UPDATE_PLAN.md          # v4.1中版本更新计划 (概要)
├── v4.1_ROADMAP.md              # 🎯 v4.1详细开发路线图 (当前执行纲领)
├── v4.1_ARCHIVE_NOTE.md         # 旧文档归档说明
└── archive_v4.0_history/        # v4.0历史文档归档
    ├── DATA_SOURCE_FIX.md
    ├── DualExpert_Guide.md
    ├── INTELLIGENCE_SYSTEM_DEV_PLAN.md
    └── INTELLIGENCE_SYSTEM_OPTIMIZATION.md
```

---

## 🎯 当前执行文档

### 必读 (开发v4.1前请阅读)
| 文档 | 说明 | 优先级 |
|------|------|--------|
| **v4.1_ROADMAP.md** | v4.1详细开发路线图，包含时间表、验收标准 | ⭐⭐⭐ |
| v4.1_UPDATE_PLAN.md | v4.1三大模块概要说明 | ⭐⭐ |

### 归档文档 (已过时，仅供参考)
| 文档 | 说明 | 状态 |
|------|------|------|
| archive_v4.0_history/INTELLIGENCE_SYSTEM_DEV_PLAN.md | 情报系统开发计划 | 已整合到v4.1_ROADMAP |
| archive_v4.0_history/INTELLIGENCE_SYSTEM_OPTIMIZATION.md | 情报系统优化方案 | 已整合到v4.1_ROADMAP |
| archive_v4.0_history/DATA_SOURCE_FIX.md | 数据源修复指南 | data_fallback.py已实现 |
| archive_v4.0_history/DualExpert_Guide.md | 双专家用户指南 | 已运行在生产环境 |

---

## 🚀 v4.1 开发快速开始

### Week 1: 底层加固
```bash
# 1. 执行数据库迁移
sqlite3 stock_data/intel_hub.db < migration_tool/migrate_v4.1_intelligence.sql

# 2. 测试多数据源回退
python utils/data_fallback.py

# 3. 验证数据源健康
python utils/data_health_monitor.py
```

### Week 2: AI功能
```bash
# 1. 测试情报分析
python scripts/intel_analyzer.py --test

# 2. 手动触发归档
python scripts/intel_archive.py --dry-run
```

### Week 3: 体验优化
```bash
# 启动应用验证ETF专属页
streamlit run main.py
```

---

## 📋 文档维护规范

1. **新增功能**: 同步更新本文档导航
2. **计划变更**: 优先更新 `v4.1_ROADMAP.md`
3. **旧文档**: 完成后移至 `archive_v4.0_history/`
4. **版本发布**: 同步更新 CHANGELOG.md

---

*本文档由AI程序员维护，确保文档与代码同步。*
