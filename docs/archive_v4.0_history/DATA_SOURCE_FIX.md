# 数据获取修复指南

## 问题
东方财富网 (EastMoney) 封了爬虫，akshare 无法获取实时数据。

## 解决方案
已创建 `utils/data_fallback.py` 提供备用数据源：
- **新浪财经** (Sina Finance) - 通常最稳定
- **腾讯财经** (Tencent Finance) - 备用

## 测试备用数据源

```bash
cd /Users/zuliangzhao/MarketMonitorAndBuyer
source venv/bin/activate
python3 utils/data_fallback.py
```

## 集成到现有代码

在 `utils/data_fetcher.py` 中修改 `get_stock_realtime_info()` 函数：

```python
# 在文件顶部导入
from utils.data_fallback import get_stock_spot_with_fallback

# 修改 get_stock_realtime_info 函数
def get_stock_realtime_info(symbol: str) -> Optional[Dict]:
    """
    [Enhanced with Fallback]
    Try multiple data sources to get real-time stock info.
    """
    # First try the new fallback system
    data = get_stock_spot_with_fallback(symbol)
    if data:
        return data
    
    # If all sources fail, use existing offline logic
    # ... (existing code)
```

## 获取全市场列表的替代方案

如果 `ak.stock_zh_a_spot_em()` 也无法使用，可以：

1. **使用本地缓存** — 股票列表变化不频繁，可以用缓存
2. **使用其他 API** — 如腾讯财经的股票列表接口
3. **手动维护股票列表** — 将常用股票保存在本地文件

## 建议

1. 东方财富的封锁通常是暂时的，可以等待几天再试
2. 建议同时接入多个数据源以提高可靠性
3. 优先使用本地缓存，减少 API 调用频率

## 当前状态

- ✅ 新浪财经 API: 可用
- ✅ 腾讯财经 API: 可用
- ❌ 东方财富 (akshare): 暂时被封
- ✅ 本地缓存: 可用
