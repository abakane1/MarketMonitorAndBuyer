# 📁 项目目录结构说明

> 整理时间: 2026-03-14  
> 原则: 根目录保持简洁，分类存放

```
MarketMonitorAndBuyer/
│
├── 📄 核心文件 (保持在根目录)
│   ├── main.py                 # 主程序入口
│   ├── README.md               # 项目说明
│   ├── CHANGELOG.md            # 版本更新日志
│   ├── VERSION                 # 当前版本号
│   ├── requirements.txt        # Python依赖
│   ├── user_config.json        # 用户配置
│   └── watchlist.json          # 自选股列表
│
├── 📊 架构文档
│   ├── ARCHITECTURE_v4.md      # v4架构设计
│   └── SYSTEM_ISSUES_TODO.md   # 问题跟踪
│
├── 📦 源码目录
│   ├── components/             # UI组件 (Streamlit)
│   ├── pages/                  # 多页面路由
│   ├── utils/                  # 工具函数
│   ├── data_platform/          # 数据中台
│   ├── capability_platform/    # 能力中台
│   └── prompts/                # AI提示词
│
├── 🔧 脚本目录
│   └── scripts/                # 各种脚本
│       ├── start.sh            # 启动脚本
│       ├── stop.sh             # 停止脚本
│       ├── *.py                # 工具脚本
│       └── *.sh                # Shell脚本
│
├── 🧪 测试目录
│   └── tests/                  # 测试文件
│       ├── test_*.py           # 单元测试
│       └── conftest.py         # pytest配置
│
├── 📚 文档目录
│   └── docs/                   # 项目文档
│       ├── v4.1_ROADMAP.md     # v4.1开发路线图
│       ├── v4.1_STATUS.md      # 项目状态
│       ├── archive_v4.0_history/  # v4.0历史文档
│       └── archive_root/       # 根目录归档文档
│
├── 🚀 部署目录
│   └── deploy/                 # 部署相关
│       ├── Dockerfile
│       └── docker-compose.yml
│
├── 💾 数据目录
│   ├── stock_data/             # 股票数据
│   ├── data/                   # 应用数据
│   ├── logs/                   # 日志文件
│   └── reports/                # 报告输出
│
├── 🔧 工具目录
│   ├── migration_tool/         # 数据库迁移
│   ├── debug/                  # 调试文件
│   └── archive/                # 归档文件
│
└── ⚙️ 环境目录
    ├── venv/                   # Python虚拟环境
    └── config/                 # 配置文件模板
```

---

## 📋 文件存放规范

### ✅ 应该放在根目录的
- 入口文件 (`main.py`)
- 说明文档 (`README.md`, `CHANGELOG.md`)
- 版本标记 (`VERSION`)
- 依赖文件 (`requirements.txt`)
- 用户配置 (`user_config.json`, `watchlist.json`)

### ❌ 不应该放在根目录的
- 脚本文件 → 移到 `scripts/`
- 测试文件 → 移到 `tests/`
- 日志文件 → 移到 `logs/`
- 备份文件 → 移到 `archive/` 或删除
- Docker文件 → 移到 `deploy/`
- 旧文档 → 移到 `docs/archive/`

---

## 🔍 快速查找

| 查找内容 | 路径 |
|---------|------|
| 启动系统 | `scripts/start.sh` 或 `python main.py` |
| 查看日志 | `logs/*.log.latest` |
| 运行测试 | `pytest tests/` |
| 数据库迁移 | `migration_tool/` |
| v4.1开发计划 | `docs/v4.1_ROADMAP.md` |
| 问题跟踪 | `SYSTEM_ISSUES_TODO.md` |

---

*保持根目录整洁，提高开发效率！*
