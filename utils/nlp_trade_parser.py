# -*- coding: utf-8 -*-
"""
自然语言交易指令解析器 (NLP Trade Parser)
支持多种自然语言表达方式，智能提取交易要素
"""

import re
from typing import Dict, Optional
from utils.data_fetcher import get_stock_realtime_info


def parse_natural_language_trade(text: str, api_key: str = None) -> Dict:
    """
    使用NLP解析自然语言交易指令
    
    支持的表达方式：
    - "帮我买1000股588200"
    - "卖出300股600076，价格4.5"
    - "588200买入1000股"
    - "清仓600076"
    - "600076 4.5元买入1000股"
    - "加仓588200 5000股"
    - "减仓600076一半"
    - "市价买入588200 1000股"
    
    返回：
    {
        "symbol": str,        # 股票代码
        "action": str,        # "buy" or "sell"
        "quantity": int,      # 数量（股）
        "price": float,       # 价格（可选，默认市价）
        "order_type": str,    # "limit" or "market"
        "valid": bool,        # 是否解析成功
        "error": str,         # 错误信息
        "parsed_by": str      # "rule" or "ai" (使用的解析方式)
    }
    """
    text = text.strip()
    result = {
        "symbol": None,
        "action": None,
        "quantity": None,
        "price": None,
        "order_type": "limit",
        "valid": False,
        "error": None,
        "parsed_by": "rule"
    }
    
    if not text:
        result["error"] = "请输入交易指令"
        return result
    
    # 1. 提取股票代码（6位数字）
    symbol = _extract_symbol(text)
    if not symbol:
        result["error"] = "未能识别股票代码（需要6位数字，如588200）"
        return result
    result["symbol"] = symbol
    
    # 2. 提取交易方向（买/卖）
    action = _extract_action(text)
    if not action:
        result["error"] = "未能识别交易方向（买/卖/加仓/减仓/清仓）"
        return result
    result["action"] = action
    
    # 3. 提取数量
    quantity = _extract_quantity(text, action)
    if quantity is None:
        result["error"] = "未能识别交易数量（如：1000股、2手）"
        return result
    result["quantity"] = quantity
    
    # 4. 提取价格（可选）
    price, order_type = _extract_price(text)
    result["price"] = price
    result["order_type"] = order_type
    
    # 5. 如果没有指定价格，尝试获取实时价格
    if price is None:
        info = get_stock_realtime_info(symbol)
        if info and info.get('price'):
            result["price"] = info['price']
            result["note"] = f"使用实时价格: {info['price']}"
        else:
            result["error"] = f"未能获取{symbol}实时价格，请手动输入"
            return result
    
    # 6. 验证
    if result["quantity"] <= 0:
        result["error"] = "交易数量必须大于0"
        return result
    
    if result["quantity"] % 100 != 0:
        result["error"] = "A股交易数量必须是100的整数倍（1手=100股）"
        return result
    
    if result["price"] <= 0:
        result["error"] = "交易价格必须大于0"
        return result
    
    result["valid"] = True
    return result


def _extract_symbol(text: str) -> Optional[str]:
    """提取6位股票代码"""
    # 匹配6位连续数字（使用原始字符串）
    match = re.search(r'(\d{6})', text)
    if match:
        code = match.group(1)
        # 简单验证：A股代码通常以0/3/6开头，ETF以5/1开头
        if code[0] in '013568':
            return code
    return None


def _extract_action(text: str) -> Optional[str]:
    """提取交易方向"""
    text = text.lower()
    
    # 买入关键词
    buy_keywords = ['买', 'buy', '加仓', '建仓', '开仓', '做多', '抄底', '补仓']
    # 卖出关键词
    sell_keywords = ['卖', 'sell', '减仓', '清仓', '平仓', '止盈', '止损', '做空', '出']
    
    for kw in buy_keywords:
        if kw in text:
            return "buy"
    
    for kw in sell_keywords:
        if kw in text:
            return "sell"
    
    # 特殊处理：如果包含"全部"、"所有"、"一半"等，结合语境判断
    if any(w in text for w in ['全部', '所有', '清仓', '清掉']):
        return "sell"
    
    return None


def _extract_quantity(text: str, action: str) -> Optional[int]:
    """提取交易数量"""
    text = text.lower()
    
    # 模式1: "X股" / "X手"
    match = re.search(r'(\d+)\s*[股手]', text)
    if match:
        qty = int(match.group(1))
        # 如果是"手"，转换为股
        if '手' in text[match.end()-5:match.end()+5]:
            qty *= 100
        return qty
    
    # 模式2: "X万"股
    match = re.search(r'(\d+(?:\.\d+)?)\s*万股', text)
    if match:
        return int(float(match.group(1)) * 10000)
    
    # 模式3: 纯数字（后面没有单位，但上下文是交易）
    # 提取所有数字，选择合理的数量（>=100且是100的倍数）
    numbers = re.findall(r'\d+', text)
    for num_str in numbers:
        num = int(num_str)
        if num >= 100 and num % 100 == 0:
            # 排除可能是价格的数字（通常有小数点或比较小）
            # 如果数字大于1000，很可能是数量
            if num > 1000:
                return num
    
    # 模式4: "一半"、"半仓" - 这需要持仓信息，暂不支持具体数值，返回标记
    if any(w in text for w in ['一半', '半仓', '50%', '五成']):
        return -1  # 特殊标记，表示需要计算
    
    # 模式5: "全部"、"所有"、"清仓" - 这也需要持仓信息
    if any(w in text for w in ['全部', '所有', '清仓', '清掉', '全卖']):
        return -2  # 特殊标记，表示全部持仓
    
    return None


def _extract_price(text: str) -> tuple:
    """提取交易价格，返回(价格, 订单类型)"""
    text = text.lower()
    
    # 市价关键词
    if any(w in text for w in ['市价', '市场价', '现价', 'market', '当前价']):
        return None, "market"
    
    # 模式1: "X元" / "X块" / "X.price"
    patterns = [
        r'(\d+\.\d{1,4})\s*[元块]',  # 2.435元
        r'(\d+\.\d{1,4})\s*[左右]?',  # 2.435
        r'价格[为是:]?\s*(\d+\.\d{1,4})',  # 价格为2.435
        r'@(\d+\.\d{1,4})',  # @2.435
        r'at\s+(\d+\.\d{1,4})',  # at 2.435
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price = float(match.group(1))
            return price, "limit"
    
    return None, "limit"


def format_trade_summary(parsed: Dict) -> str:
    """格式化交易摘要，用于确认显示"""
    if not parsed["valid"]:
        return f"❌ 解析失败: {parsed['error']}"
    
    action_cn = "买入" if parsed["action"] == "buy" else "卖出"
    order_type_cn = "市价" if parsed["order_type"] == "market" else "限价"
    
    # 处理特殊数量标记
    qty = parsed["quantity"]
    if qty == -1:
        qty_display = "半仓（根据持仓计算）"
        amount_display = "根据实际持仓计算"
    elif qty == -2:
        qty_display = "全部持仓（清仓）"
        amount_display = "根据实际持仓计算"
    else:
        qty_display = f"**{qty:,}股** ({qty//100}手)"
        amount_display = f"**{parsed['price'] * qty:,.0f}元**"
    
    summary = f"""
**交易确认**
| 项目 | 内容 |
|------|------|
| 股票代码 | **{parsed['symbol']}** |
| 交易方向 | **{action_cn}** |
| 交易数量 | {qty_display} |
| 订单类型 | **{order_type_cn}** |
| 交易价格 | **{parsed['price']:.3f}元** |
| 预计金额 | {amount_display} |
"""
    return summary


# 兼容旧接口
def parse_trade_command(text: str) -> Dict:
    """
    兼容旧版接口，调用新的NLP解析器
    """
    return parse_natural_language_trade(text)


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "帮我买1000股588200",
        "卖出300股600076，价格4.5",
        "588200买入1000股",
        "市价买入588200 5000股",
        "600076 4.5元买入1000股",
        "加仓588200 5000股",
        "减仓600076一半",
        "清仓600076",
        "帮我卖掉588200全部持仓",
    ]
    
    print("=== NLP交易指令解析测试 ===\n")
    for cmd in test_cases:
        result = parse_natural_language_trade(cmd)
        print(f"指令: {cmd}")
        if result["valid"]:
            print(f"  ✓ 解析成功: {result['action']} {result['symbol']} {result['quantity']}股 @ {result['price']}")
        else:
            print(f"  ✗ 解析失败: {result['error']}")
        print()
