# TODO 列表 (待办事项)

## 下一版本 (Next Version v1.3.1)

### 1. 遗留任务补全 (Completing v1.2.2 Tasks)
- [ ] **完善交易哲学 (Prompt)**:
    - 检查发现 `user_config.json.example` 中缺失 "**别人恐惧我贪婪，别人贪婪我恐惧**" 的心态描述。
    - 需在 `deepseek_base` 提示词中正式补全此逻辑。

### 2. AI 盯盘增强 (AI Monitoring & Backtesting)
- [ ] **前台可视化 AI 盯盘**:
    - 目前 AI 盯盘逻辑（如果存在后台进程）在前台不可见。
    - 新增一个 UI 组件或页面，实时展示 AI 对当前分钟数据的研判状态、心跳和最新决策。
- [ ] **全天候动态回测 (Full-day Dynamic Loop)**:
    - 修正回测逻辑：目前的模拟是单次生成策略后执行。
    - 改进为：AI 像真实环境一样，从开盘到收盘**全程**“盯着”盘面，根据每分钟/每十分钟的变化动态更新策略，而不仅仅是盘前一次决策。

### 3. 代码重构与架构 (Refactoring - Continued)
- [ ] **继续重构 `main.py`**:
    - 拆分主控制面板至 `components/dashboard.py`
    - 拆分 AI/策略区域至 `components/strategy_section.py`

---

## 已完成 (Completed in v1.3.0)

### 1. 代码重构与架构
- [x] **组件化拆分**: 
    - 创建 `components/` 目录
    - 拆分侧边栏逻辑至 `components/sidebar.py`
- [x] **消除硬编码日期**: `sim_ui.py` 支持动态日期选择

### 2. 测试体系
- [x] **引入 Pytest**:
    - `tests/conftest.py`, `tests/test_strategy.py`, `tests/test_data_fetcher.py` (28 passed)

### 3. 数据健壮性
- [x] **优化错误处理**: 自定义异常类 + logging 集成

---

## 已完成 (Completed in v1.2.2)
- [x] **优化分时明细吸收**: 已在 `utils/data_fetcher.py` 实现 `analyze_intraday_pattern`。
