def is_etf(symbol: str) -> bool:
    """
    判断指定的证券代码是否为 ETF (被动基金)。
    基于 A 股常见代码段进行粗略判定：
    - 51xxxx: 上交所 ETF
    - 15xxxx: 深交所 ETF
    - 56xxxx: 上交所 ETF (部分)
    - 588xxx: 科创板 ETF
    """
    if not symbol:
        return False
        
    symbol_str = str(symbol).strip()
    
    # 获取纯数字代码部分，忽略前缀如 sh/sz 等
    import re
    match = re.search(r'\d{6}', symbol_str)
    if not match:
        return False
        
    code = match.group(0)
    
    if code.startswith('51') or code.startswith('15') or code.startswith('56') or code.startswith('588'):
        return True
        
    return False

def get_asset_type_and_tags(symbol: str) -> dict:
    """
    获取资产的全方位定性标签，供 AI 决策引擎和 UI 看板使用。
    """
    is_fund = is_etf(symbol)
    
    if is_fund:
        return {
            "type": "etf",
            "strategy": "long_term",
            "badge": "🛡️ 长线定投模式 (ETF)",
            "description": "被动宽基/行业基金，具备大盘系统性贝塔，适合长线钝化持有、向下越跌越买（定投/网格）。"
        }
    else:
        return {
            "type": "stock",
            "strategy": "short_term",
            "badge": "⚔️ 短线猎杀模式 (Stock)",
            "description": "个股标的，适合捕捉短期情绪和资金动量。容错率低，需要严格的纪律性风控（技术止损）和灵活进出。"
        }
