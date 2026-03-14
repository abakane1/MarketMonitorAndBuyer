# v4.0 迁移指南

## 概述

本文档帮助开发者从 v3.x 迁移到 v4.0 的架构。

## 主要变化

### 1. 数据操作方式变化

**旧方式 (v3.x):**
```python
from utils.database import db_get_position, db_update_position
from utils.config import update_position

# 获取持仓
pos = db_get_position('588200')

# 更新持仓（分散在多个地方）
update_position('588200', shares, price, 'buy')
```

**新方式 (v4.0):**
```python
from data_platform import PositionService, PositionModel
from data_platform.models import TradeAction
from capability_platform.calculators import PositionCalculator

# 获取持仓
service = PositionService()
position = service.get('588200')

# 计算新持仓
new_shares, new_cost = PositionCalculator.calculate_new_position(
    current_shares=position.shares,
    current_cost=position.cost,
    action=TradeAction.BUY,
    trade_price=2.50,
    trade_amount=1000
)

# 保存新持仓
new_position = position.with_new_cost(new_shares, new_cost)
service.save(new_position)
```

### 2. 交易执行方式变化

**旧方式 (v3.x):**
```python
from utils.trade_manager import execute_trade

result = execute_trade('588200', 'buy', 2.50, 1000)
```

**新方式 (v4.0):**
```python
from data_platform import TradeService, TradeModel
from data_platform.models import TradeAction

# 创建交易模型
trade = TradeModel(
    symbol='588200',
    action=TradeAction.BUY,
    price=2.50,
    amount=1000,
    note='快速交易'
)

# 执行交易
service = TradeService()
success, msg, result = service.execute(trade)
```

### 3. 费率计算方式变化

**旧方式 (v3.x):**
```python
# 分散在多个地方的硬编码计算
fee = round(trade_value * 0.0003, 2)
stamp_duty = round(trade_value * 0.0001, 2) if is_sell else 0.0
```

**新方式 (v4.0):**
```python
from capability_platform.calculators import FeeCalculator

fees = FeeCalculator.calculate(
    symbol='588200',
    price=2.50,
    amount=1000,
    is_sell=False
)
# fees = {'fee': 5.0, 'stamp_duty': 0.0, 'transfer_fee': 0.0, 'total': 5.0}
```

### 4. 盈亏计算方式变化

**旧方式 (v3.x):**
```python
# UI层直接计算
today_pnl = (current_price - pre_close) * shares
floating_pnl = (current_price - cost) * shares
```

**新方式 (v4.0):**
```python
from capability_platform.calculators import PnLCalculator

# 使用统一计算器
today_pnl = PnLCalculator.calculate_today_pnl(shares, current_price, pre_close)
floating_pnl = PnLCalculator.calculate_floating_pnl(shares, cost, current_price)

# 或者从模型直接计算
position = PositionModel(...)
today_pnl = position.today_pnl(current_price, pre_close)
floating_pnl = position.floating_pnl(current_price)
```

## 逐步迁移步骤

### 步骤 1: 更新导入语句

将旧导入：
```python
from utils.database import db_get_position, db_update_position, db_add_history
from utils.config import update_position, recalculate_position_from_history
```

改为新导入：
```python
from data_platform import PositionService, TradeService
from data_platform.models import PositionModel, TradeModel, TradeAction
from capability_platform.calculators import PositionCalculator, FeeCalculator, PnLCalculator
```

### 步骤 2: 替换持仓操作

**旧代码:**
```python
pos = db_get_position(symbol)
current_shares = pos["shares"]
current_cost = pos["cost"]
# ... 计算 ...
db_update_position(symbol, new_shares, new_cost, base_shares)
```

**新代码:**
```python
service = PositionService()
position = service.get(symbol)
if position:
    new_shares, new_cost = PositionCalculator.calculate_new_position(...)
    new_position = position.with_new_cost(new_shares, new_cost)
    service.save(new_position)
```

### 步骤 3: 替换交易记录

**旧代码:**
```python
db_add_history(symbol, timestamp, 'buy', price, amount, note)
```

**新代码:**
```python
trade = TradeModel(
    symbol=symbol,
    action=TradeAction.BUY,
    price=price,
    amount=amount,
    note=note
)
service = TradeService()
service.execute(trade)
```

### 步骤 4: 修复数据不一致

如果发现持仓和交易记录不一致：

```python
from data_platform import PositionService

service = PositionService()

# 重新计算指定标的的持仓
position = service.recalculate_from_history('588200')

# 重新计算所有持仓
from utils.database import db_get_watchlist
watchlist = db_get_watchlist()
for symbol in watchlist:
    service.recalculate_from_history(symbol)
```

## 数据一致性检查

迁移后，运行以下检查确保数据一致性：

```python
from data_platform import PositionService, TradeService
from capability_platform.calculators import PositionCalculator

def check_position_consistency(symbol: str) -> bool:
    '''检查持仓是否与交易记录一致'''
    position_service = PositionService()
    trade_service = TradeService()
    
    # 获取当前持仓
    current = position_service.get(symbol)
    
    # 从交易历史重新计算
    trades = trade_service.get_history(symbol)
    expected_shares, expected_cost, _ = PositionCalculator.recalculate_from_trades(trades)
    
    # 比较
    if current.shares != expected_shares or abs(current.cost - expected_cost) > 0.0001:
        print(f"{symbol} 不一致:")
        print(f"  当前: {current.shares}股 @ {current.cost:.4f}")
        print(f"  计算: {expected_shares}股 @ {expected_cost:.4f}")
        return False
    
    return True

# 检查所有持仓
from utils.database import db_get_all_positions
positions = db_get_all_positions()
for pos in positions:
    check_position_consistency(pos['symbol'])
```

## 常见问题

### Q: 为什么要引入数据中台？

A: 在 v3.x 中，同一个数据（如持仓成本）有多个计算来源，导致不一致。v4.0 通过数据中台确保所有数据操作都经过统一的 Service 层，实现单一事实来源。

### Q: 如何回滚到旧版本？

A: 数据库结构完全兼容，只需回滚代码到 v3.x 分支即可。但建议使用 v4.0 的新架构。

### Q: 性能有变化吗？

A: v4.0 增加了缓存层，性能有所提升。所有 Service 都有 5 秒缓存，减少数据库查询。

### Q: 如何添加新的计算逻辑？

A: 所有计算都应该放在 `capability_platform/calculators/` 中，避免在 UI 层直接计算。

## 迁移检查清单

- [ ] 更新所有 `db_get_position` 调用
- [ ] 更新所有 `db_update_position` 调用
- [ ] 更新所有 `db_add_history` 调用
- [ ] 更新所有费率计算
- [ ] 更新所有盈亏计算
- [ ] 运行数据一致性检查
- [ ] 测试交易执行流程
- [ ] 测试持仓重新计算功能

## 支持

如遇到迁移问题，请查看：
1. `ARCHITECTURE_v4.md` - 架构设计文档
2. 代码注释和 docstring
3. 示例代码（tests/ 目录）
