# MarketMonitorAndBuyer v4.0 架构设计

## 版本信息
- **版本**: 4.0.0
- **代号**: Unified Platform (统一平台)
- **日期**: 2026-03-09
- **目标**: 解决数据不一致、算法分散问题，建立数据中台和能力中台

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用层 (Applications)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  Streamlit UI  │  批量策略  │  自动交易  │  监控告警  │  策略实验室      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            能力中台 (Capability Platform)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  计算引擎   │  │  分析引擎   │  │  策略引擎   │  │  风控引擎   │       │
│  │  Calculator│  │  Analytics │  │  Strategy  │  │   Risk     │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  交易引擎   │  │  回测引擎   │  │  AI 引擎   │  │  通知引擎   │       │
│  │   Trade    │  │  Backtest  │  │    AI      │  │ Notification│       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             数据中台 (Data Platform)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        统一数据模型层                                │   │
│  │   Position │ Trade │ History │ Quote │ Market │ Intel │ Strategy  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────┐  ┌──────────────────────────┐                 │
│  │      数据存储层          │  │      数据缓存层          │                 │
│  │  SQLite (Primary)       │  │  Memory Cache           │                 │
│  │  Parquet (Time Series)  │  │  Disk Cache             │                 │
│  │  JSON (Config)          │  │  DataFrame Cache        │                 │
│  └──────────────────────────┘  └──────────────────────────┘                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        数据接入层 (Adapters)                         │   │
│  │   Sina │ Tencent │ AKShare │ EFinance │ Local File │ Mock          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心设计原则

### 2.1 单一事实来源 (Single Source of Truth)
- 所有持仓数据来自 `PositionModel`
- 所有交易记录来自 `TradeModel`
- 所有行情数据来自 `QuoteModel`
- 禁止直接操作数据库，必须通过 DataService

### 2.2 算法统一 (Unified Algorithms)
- 成本计算：统一使用加权平均法
- 盈亏计算：统一使用移动平均成本法
- 费率计算：统一通过 FeeCalculator
- 时间处理：统一通过 TimeUtils

### 2.3 能力复用 (Capability Reuse)
- 计算逻辑集中在 Calculator
- 分析逻辑集中在 Analytics
- 交易逻辑集中在 TradeEngine
- 禁止在 UI 层直接计算

---

## 3. 数据中台 (Data Platform)

### 3.1 目录结构
```
data_platform/
├── __init__.py
├── models/                    # 统一数据模型
│   ├── __init__.py
│   ├── base.py               # 基础模型类
│   ├── position.py           # 持仓模型
│   ├── trade.py              # 交易模型
│   ├── quote.py              # 行情模型
│   ├── history.py            # 历史记录模型
│   ├── portfolio.py          # 投资组合模型
│   └── intelligence.py       # 情报模型
├── services/                  # 数据服务层
│   ├── __init__.py
│   ├── base_service.py       # 基础服务类
│   ├── position_service.py   # 持仓服务
│   ├── trade_service.py      # 交易服务
│   ├── quote_service.py      # 行情服务
│   ├── history_service.py    # 历史服务
│   └── cache_service.py      # 缓存服务
├── adapters/                  # 数据接入适配器
│   ├── __init__.py
│   ├── base_adapter.py
│   ├── sina_adapter.py
│   ├── tencent_adapter.py
│   ├── akshare_adapter.py
│   └── local_adapter.py
├── validators/                # 数据校验
│   ├── __init__.py
│   ├── trade_validator.py
│   └── quote_validator.py
└── sync.py                    # 数据同步器
```

### 3.2 核心模型定义

#### PositionModel (持仓)
```python
@dataclass
class PositionModel:
    symbol: str
    shares: int          # 当前持股数
    cost: float          # 成本价（加权平均）
    base_shares: int     # 底仓数
    portfolio_id: str
    updated_at: datetime
    
    # 计算属性（只读）
    @property
    def market_value(self, current_price: float) -> float:
        return self.shares * current_price
    
    @property
    def floating_pnl(self, current_price: float) -> float:
        return self.shares * (current_price - self.cost)
```

#### TradeModel (交易)
```python
@dataclass
class TradeModel:
    id: Optional[int]
    symbol: str
    timestamp: datetime
    action: TradeAction   # BUY / SELL / OVERRIDE
    price: float
    amount: int
    fee: float
    stamp_duty: float
    transfer_fee: float
    note: str
    portfolio_id: str
    
    @property
    def total_value(self) -> float:
        return self.price * self.amount
    
    @property
    def total_cost(self) -> float:
        return self.total_value + self.fee + self.stamp_duty + self.transfer_fee
```

#### QuoteModel (行情)
```python
@dataclass
class QuoteModel:
    symbol: str
    name: str
    price: float         # 最新价
    pre_close: float     # 昨收
    open: float
    high: float
    low: float
    volume: float
    amount: float
    change_pct: float    # 涨跌幅
    timestamp: datetime
    source: str          # 数据来源
    
    @property
    def today_pnl_per_share(self) -> float:
        return self.price - self.pre_close
```

### 3.3 数据服务接口

```python
class PositionService:
    """持仓服务 - 所有持仓操作的唯一入口"""
    
    def get(self, symbol: str, portfolio_id: str = "default") -> PositionModel
    def get_all(self, portfolio_id: str = "default") -> List[PositionModel]
    def update(self, position: PositionModel) -> bool
    def recalculate_from_history(self, symbol: str) -> PositionModel
    
class TradeService:
    """交易服务 - 所有交易记录的唯一入口"""
    
    def record(self, trade: TradeModel) -> Tuple[bool, str]
    def get_history(self, symbol: str, limit: int = None) -> List[TradeModel]
    def delete(self, trade_id: int) -> bool
    def validate(self, trade: TradeModel) -> Tuple[bool, str]
    
class QuoteService:
    """行情服务 - 所有行情数据的唯一入口"""
    
    def get_realtime(self, symbol: str) -> QuoteModel
    def get_batch(self, symbols: List[str]) -> Dict[str, QuoteModel]
    def get_history_kline(self, symbol: str, days: int) -> pd.DataFrame
    def refresh_cache(self, symbols: List[str])
```

---

## 4. 能力中台 (Capability Platform)

### 4.1 目录结构
```
capability_platform/
├── __init__.py
├── calculators/               # 计算引擎
│   ├── __init__.py
│   ├── position_calculator.py    # 持仓计算
│   ├── pnl_calculator.py         # 盈亏计算
│   ├── fee_calculator.py         # 费率计算
│   └── risk_calculator.py        # 风险计算
├── analytics/                 # 分析引擎
│   ├── __init__.py
│   ├── trend_analyzer.py
│   ├── volatility_analyzer.py
│   └── market_analyzer.py
├── strategies/                # 策略引擎
│   ├── __init__.py
│   ├── base_strategy.py
│   ├── grid_strategy.py
│   └── t_strategy.py
├── risk/                      # 风控引擎
│   ├── __init__.py
│   ├── trade_limit.py
│   ├── position_limit.py
│   └── alert_manager.py
├── ai/                        # AI 引擎
│   ├── __init__.py
│   ├── advisor.py
│   ├── parser.py
│   └── reviewer.py
├── trade/                     # 交易引擎
│   ├── __init__.py
│   ├── executor.py
│   └── simulator.py
└── common/                    # 公共能力
    ├── __init__.py
    ├── time_utils.py
    ├── math_utils.py
    └── validators.py
```

### 4.2 统一计算接口

```python
class PositionCalculator:
    """持仓计算器 - 统一持仓计算逻辑"""
    
    @staticmethod
    def calculate_new_position(
        current_shares: int,
        current_cost: float,
        action: TradeAction,
        trade_price: float,
        trade_amount: int
    ) -> Tuple[int, float]:
        """
        统一持仓计算逻辑
        买入：加权平均成本
        卖出：摊薄成本法
        """
        if action == TradeAction.BUY:
            total_value = current_shares * current_cost + trade_amount * trade_price
            new_shares = current_shares + trade_amount
            new_cost = total_value / new_shares if new_shares > 0 else 0.0
        elif action == TradeAction.SELL:
            current_total_cost = current_shares * current_cost
            sell_revenue = trade_amount * trade_price
            new_total_cost = current_total_cost - sell_revenue
            new_shares = current_shares - trade_amount
            new_cost = new_total_cost / new_shares if new_shares > 0 else 0.0
        
        return new_shares, round(new_cost, 4)

class PnLCalculator:
    """盈亏计算器 - 统一盈亏计算逻辑"""
    
    @staticmethod
    def calculate_floating_pnl(shares: int, cost: float, current_price: float) -> float:
        return shares * (current_price - cost)
    
    @staticmethod
    def calculate_today_pnl(shares: int, current_price: float, pre_close: float) -> float:
        return shares * (current_price - pre_close)
    
    @staticmethod
    def calculate_realized_pnl(trades: List[TradeModel]) -> Dict:
        """使用移动平均成本法计算已实现盈亏"""
        # 统一算法实现
        pass

class FeeCalculator:
    """费率计算器 - 统一费率计算逻辑"""
    
    ETF_RATE = 0.0001    # 万1
    STOCK_RATE = 0.0003  # 万3
    MIN_FEE = 5.0
    
    @classmethod
    def calculate(cls, symbol: str, price: float, amount: int, is_sell: bool) -> Dict:
        from utils.asset_classifier import is_etf
        
        trade_value = price * amount
        
        if is_etf(symbol):
            fee = max(cls.MIN_FEE, round(trade_value * cls.ETF_RATE, 2))
            stamp_duty = 0.0
            transfer_fee = 0.0
        else:
            fee = max(cls.MIN_FEE, round(trade_value * cls.STOCK_RATE, 2))
            stamp_duty = round(trade_value * 0.0005, 2) if is_sell else 0.0
            transfer_fee = round(trade_value * 0.00001, 2)
        
        return {
            'fee': fee,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'total': fee + stamp_duty + transfer_fee
        }
```

---

## 5. 迁移计划

### Phase 1: 基础设施 (Week 1)
- [ ] 创建 data_platform 目录结构
- [ ] 创建 capability_platform 目录结构
- [ ] 定义统一数据模型
- [ ] 实现基础服务类

### Phase 2: 数据层迁移 (Week 2)
- [ ] 迁移 Position 相关操作到 PositionService
- [ ] 迁移 Trade 相关操作到 TradeService
- [ ] 迁移 Quote 相关操作到 QuoteService
- [ ] 统一缓存管理

### Phase 3: 计算层迁移 (Week 3)
- [ ] 迁移持仓计算到 PositionCalculator
- [ ] 迁移盈亏计算到 PnLCalculator
- [ ] 迁移费率计算到 FeeCalculator
- [ ] 统一所有计算入口

### Phase 4: 业务层迁移 (Week 4)
- [ ] 重构 portfolio.py 使用中台
- [ ] 重构 dashboard.py 使用中台
- [ ] 重构 trade_manager.py 使用中台
- [ ] 删除旧的分散逻辑

### Phase 5: 测试与优化 (Week 5)
- [ ] 编写数据一致性测试
- [ ] 编写算法正确性测试
- [ ] 性能测试与优化
- [ ] 文档更新

---

## 6. 数据一致性检查清单

### 持仓数据
- [ ] positions 表与 trade history 一致性
- [ ] 成本价计算一致性
- [ ] 持股数量一致性

### 交易数据
- [ ] 手续费计算一致性
- [ ] 交易类型标记一致性
- [ ] 时间戳格式一致性

### 行情数据
- [ ] 昨收价格来源一致性
- [ ] 涨跌幅计算一致性
- [ ] 数据时效性一致性

### 盈亏数据
- [ ] 浮动盈亏计算一致性
- [ ] 今日盈亏计算一致性
- [ ] 已实现盈亏计算一致性

---

## 7. 接口契约

### 7.1 数据服务契约
```python
# 所有服务必须实现以下接口
class BaseService(ABC):
    @abstractmethod
    def get(self, id: str) -> BaseModel:
        pass
    
    @abstractmethod
    def save(self, model: BaseModel) -> bool:
        pass
    
    @abstractmethod
    def validate(self, model: BaseModel) -> Tuple[bool, str]:
        pass
```

### 7.2 计算引擎契约
```python
# 所有计算器必须是纯函数，无副作用
class BaseCalculator(ABC):
    @staticmethod
    @abstractmethod
    def calculate(*args, **kwargs) -> Any:
        pass
```

---

## 8. 版本更新记录

### [4.0.0] - 2026-03-09
#### 架构升级
- 引入数据中台，统一数据管理
- 引入能力中台，统一算法逻辑
- 建立单一事实来源，消除数据不一致
- 建立统一计算引擎，消除算法不一致
#### 新增模块
- `data_platform/` - 数据中台
- `capability_platform/` - 能力中台
#### 重构模块
- 重构所有数据操作使用 Service 层
- 重构所有计算逻辑使用 Calculator
- 删除 utils/config.py 中的分散逻辑
