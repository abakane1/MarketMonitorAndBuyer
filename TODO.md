# TODO 列表 (待办事项)



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
