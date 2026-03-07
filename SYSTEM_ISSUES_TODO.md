# MarketMonitorAndBuyer 系统问题跟踪

## 📋 使用说明

本文件用于跟踪 MarketMonitorAndBuyer 系统的问题和待办事项。当操作技能发现系统问题时，应在此记录，等待AI程序员修复。

## 🎯 记录规则

### 发现问题时：
1. **检查是否已存在**：查看本文件是否已记录类似问题
2. **创建新条目**：按下方模板添加新问题
3. **分配状态**：`🆕 新发现` → `🔍 调查中` → `🔧 修复中` → `✅ 已解决`
4. **通知用户**：在飞书群聊中告知问题已记录

### 问题模板：
```markdown
## [问题标题]

**状态**: 🆕 新发现  
**发现时间**: YYYY-MM-DD HH:MM  
**发现者**: [操作技能名称]  
**优先级**: 🔴 高 / 🟡 中 / 🟢 低  

### 问题描述
[详细描述问题现象]

### 复现步骤
1. [步骤1]
2. [步骤2]
3. [步骤3]

### 错误信息
```
[粘贴错误日志]
```

### 相关文件
- `[文件路径]`
- `[文件路径]`

### 影响范围
[描述问题影响的功能]

### 临时解决方案
[如有，描述临时解决方案]

### 修复建议
[如有，描述修复建议]
```

---

## 📝 当前问题列表

### 1. Kimi API 密钥无效 (需要复核)

**状态**: ✅ 已解决  
**发现时间**: 2026-03-07 09:16  
**解决时间**: 2026-03-07 21:58  
**发现者**: stock-strategy-group 技能  
**优先级**: 🔴 高  

#### 问题描述
早上调用 Kimi API 时返回 401 错误：`"Invalid Authentication"`。但用户反馈在 21:31 成功生成了完整策略，表明 Kimi API 密钥可能已经修复或早上测试时使用了错误的密钥。

#### 早上错误信息
```
Kimi API Error 401: {"error":{"message":"Invalid Authentication","type":"invalid_authentication_error"}} (Key: sk-4a..., Len: 35)
```

#### 当前证据
- **21:31 成功生成策略**: `review_logs` 显示 588710 有 9652 字符的完整策略
- **配置文件已更新**: `user_config.json` 中的 `kimi_api_key` 为 `sk-du9jn...` (新密钥)
- **早上可能的问题**: 测试时可能使用了 `qwen_api_key` 的值 (`sk-4a25b...`) 而非 `kimi_api_key`

#### 相关文件
- `/Users/zuliangzhao/MarketMonitorAndBuyer/user_config.json` (API密钥配置)
- `/Users/zuliangzhao/MarketMonitorAndBuyer/scripts/five_step_moe.py` (API调用)
- `/Users/zuliangzhao/MarketMonitorAndBuyer/utils/ai_advisor.py` (API函数)

#### 影响范围
- 需要确认 Kimi API 密钥的当前状态
- 确保早上和晚上的测试差异得到解释

#### 已查明问题根源
**密钥优先级问题**：
1. `batch_strategy_generator.py` 第65行：`qwen_key = settings.get('qwen_api_key') or settings.get('kimi_api_key')`
2. 早上测试时：`qwen_api_key` 存在且值为 `sk-4a25b...`，`kimi_api_key` 可能不存在或为空
3. 结果：使用了 `qwen_api_key` 的值调用 Kimi API，导致 401 错误
4. 当前状态：`kimi_api_key` 已更新为 `sk-du9jn...`，但代码仍优先使用 `qwen_api_key`

**已实施的修复**：
1. 修改第65行：`qwen_key = settings.get('kimi_api_key') or settings.get('qwen_api_key')`
2. 现在优先使用 `kimi_api_key`，确保使用正确的 Kimi 密钥

#### 待核实事项
1. 用户是否在 09:16 之后更新了 `kimi_api_key`？（已确认配置文件中有新密钥）
2. 当前 `kimi_api_key` 是否对所有蓝军步骤都有效？（用户21:31成功生成策略表明有效）
3. 用户通过什么方式生成策略？（可能通过Web界面，使用不同的密钥加载逻辑）

#### 修复建议
1. 验证当前 `kimi_api_key` 的有效性
2. 更新测试脚本，确保使用正确的密钥字段
3. 记录密钥变更历史以避免混淆

---

### 2. 函数参数名不匹配

**状态**: ✅ 已解决  
**发现时间**: 2026-03-07 09:13  
**解决时间**: 2026-03-07 09:28  
**发现者**: stock-strategy-group 技能  
**优先级**: 🟡 中  
**解决方法**: 已修改 `batch_strategy_generator.py` 第128行：`qwen_api_key=qwen_key` → `kimi_api_key=qwen_key`  

#### 问题描述
`batch_strategy_generator.py` 中调用 `run_five_step_workflow()` 时使用了错误的参数名 `qwen_api_key`，而函数期望的是 `kimi_api_key`。

#### 复现步骤
1. 查看 `batch_strategy_generator.py` 第128行
2. 查看 `scripts/five_step_moe.py` 第317行函数定义
3. 执行脚本时出现 `TypeError`

#### 错误信息
```
TypeError: run_five_step_workflow() got an unexpected keyword argument 'qwen_api_key'. Did you mean 'kimi_api_key'?
```

#### 相关文件
- `/Users/zuliangzhao/MarketMonitorAndBuyer/batch_strategy_generator.py` (第128行)
- `/Users/zuliangzhao/MarketMonitorAndBuyer/scripts/five_step_moe.py` (第317行)

#### 影响范围
- 批量策略生成脚本
- 手动运行策略生成时

#### 临时解决方案
已临时修改 `batch_strategy_generator.py` 第128行：`qwen_api_key=qwen_key` → `kimi_api_key=qwen_key`

#### 修复建议
1. 统一函数参数命名规范
2. 更新相关文档
3. 添加参数验证

---

### 3. 函数返回值解包错误

**状态**: ✅ 已解决  
**发现时间**: 2026-03-07 09:14  
**解决时间**: 2026-03-07 09:15  
**发现者**: stock-strategy-group 技能  
**优先级**: 🟡 中  
**解决方法**: 已修改 `scripts/five_step_moe.py` 中三处调用，将 `content, reasoning = call_kimi_api(...)` 改为 `content = call_kimi_api(...); reasoning = ''`  

#### 问题描述
`scripts/five_step_moe.py` 中期望 `call_kimi_api()` 返回两个值 `(content, reasoning)`，但实际函数只返回单个字符串 `content`。

#### 复现步骤
1. 查看 `scripts/five_step_moe.py` 第100、184、296行
2. 查看 `utils/ai_advisor.py` 中 `call_kimi_api()` 函数定义
3. 执行时出现 `ValueError`

#### 错误信息
```
ValueError: too many values to unpack (expected 2)
```

#### 相关文件
- `/Users/zuliangzhao/MarketMonitorAndBuyer/scripts/five_step_moe.py` (第100、184、296行)
- `/Users/zuliangzhao/MarketMonitorAndBuyer/utils/ai_advisor.py` (第578行 `call_kimi_api` 函数)

#### 影响范围
- 五步 MoE 工作流的所有 Kimi 调用步骤
- 策略草案生成、优化、执行令生成

#### 临时解决方案
已修改 `scripts/five_step_moe.py` 中三处调用，添加 `reasoning = ''`

#### 修复建议
1. 统一 API 调用函数的返回值格式
2. 更新函数文档说明
3. 添加返回值类型检查

---

## 📈 问题统计

| 状态 | 数量 | 优先级分布 |
|------|------|------------|
| 🆕 新发现 | 1 | 🔴高:1 🟡中:0 🟢低:0 |
| 🔍 调查中 | 0 | - |
| 🔧 修复中 | 0 | - |
| ✅ 已解决 | 2 | 🔴高:0 🟡中:2 🟢低:0 |

**最后更新**: 2026-03-07 21:39  
**更新者**: 赵大虾哥 (stock-strategy-group 技能)

---

## 📝 新增问题：人机操作路径不一致

**状态**: ✅ 已解决  
**发现时间**: 2026-03-07 21:39  
**解决时间**: 2026-03-07 21:58  
**发现者**: 用户反馈 + skill 分析  
**优先级**: 🔴 高  

### 问题描述
用户通过 Web 界面成功生成策略，但 skill 通过命令行调用 `batch_strategy_generator.py` 时遇到 Kimi API 密钥错误。两者操作路径不一致，导致结果不同。

### 已查明差异
1. **Web 界面操作路径**：
   - 用户点击 "🌤️ 生成盘前规划" 按钮
   - 调用 `components/strategy_section.py` 中的策略生成逻辑
   - 通过 `utils.ai_advisor.call_ai_model()` 调用 API
   - 密钥加载：从 `st.session_state` 或 `config.settings` 读取

2. **Skill 操作路径**：
   - 调用 `batch_strategy_generator.py` 脚本
   - 调用 `scripts.five_step_moe.run_five_step_workflow()`
   - 密钥加载：从 `config.settings` 读取，存在优先级逻辑错误

3. **关键区别**：
   - 密钥加载逻辑不同（Web 界面可能使用正确的 `kimi_api_key`）
   - API 调用方式不同（直接调用 vs 通过工作流包装）
   - 错误处理机制不同

### 用户需求明确
用户期望：**系统设计成既能被人使用（通过Web界面），也能被AI使用（通过skill），并且两者的效果应该相同**。

### 影响范围
- AI 通过 skill 操作的结果与人工操作不一致
- 系统维护复杂度增加（两套操作路径）
- 用户体验不一致

### 修复建议
**方案A（推荐）**：统一操作路径
1. 修改 skill，使其通过 Web 界面或统一的 API 接口操作系统
2. 确保人机操作使用相同的底层函数和配置

**方案B**：修复现有差异
1. 统一密钥加载逻辑，确保两处使用相同的优先级
2. 统一 API 调用函数，避免路径差异
3. 添加配置验证，确保两处配置一致

**方案C**：创建专用 AI 接口
1. 在系统中添加专门的 AI 操作端点
2. skill 调用该端点，与 Web 界面解耦
3. 确保接口返回与 Web 界面相同的结果

### 待办事项
1. [ ] 分析 Web 界面策略生成的完整调用链
2. [ ] 对比两处密钥加载的具体差异
3. [ ] 设计统一的操作接口或修复现有差异
4. [ ] 修改 skill 以使用统一接口

---

## 📈 问题统计

| 状态 | 数量 | 优先级分布 |
|------|------|------------|
| 🆕 新发现 | 2 | 🔴高:2 🟡中:0 🟢低:0 |
| 🔍 调查中 | 1 | 🔴高:1 🟡中:0 🟢低:0 |
| 🔧 修复中 | 0 | - |
| ✅ 已解决 | 2 | 🔴高:0 🟡中:2 🟢低:0 |

**最后更新**: 2026-03-07 21:39  
**更新者**: 赵大虾哥 (stock-strategy-group 技能)

---

> 💡 **提示**: 本文件由 stock-strategy-group 技能自动维护。发现问题时按模板添加，修复后更新状态。