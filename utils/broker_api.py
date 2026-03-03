import logging
from typing import Dict, Any, Optional
from utils.notification import send_notification

def execute_broker_order(
    symbol: str, 
    action: str, 
    price: float, 
    quantity: int, 
    portfolio_id: str = "default", 
    strategy_name: str = "AI_Auto"
) -> Dict[str, Any]:
    """
    提交交易指令到券商API (此处提供抽象接口供后续对接如 QMT, 易证 等实盘或模拟盘API)。
    
    Args:
        symbol (str): 股票代码
        action (str): 买卖动作 ('buy' / 'sell')
        price (float): 委托价格
        quantity (int): 委托数量(股)
        portfolio_id (str): 资金账户/组合ID
        strategy_name (str): 触发策略标识
        
    Returns:
        dict: 报单结果包含 success, order_id, message 等字段。
    """
    # [TO-DO] 真实券商 API 接入逻辑写在这里.
    # e.g., broker.submit_order(symbol, limit_price=price, amount=quantity, side=action)
    
    # 当前为模拟打桩阶段
    order_id = f"MOCK_{portfolio_id}_{symbol}_{action.upper()}"
    msg = f"已模拟向券商发送委托: {action.upper()} {symbol} {quantity}股 @ ￥{price:.3f}"
    logging.info(f"[Broker API] {msg}")
    
    # 附带一个通知
    if action == "buy":
        title = "🟢 券商委托: 买入指令"
    else:
        title = "🔴 券商委托: 卖出指令"
        
    notify_msg = f"**标的:** {symbol}\n**数量:** {quantity} 股\n**价格:** ￥{price:.3f}\n**策略:** {strategy_name}\n**账户组合:** {portfolio_id}\n\n*状态: 模拟单提交成功*"
    
    send_notification(title, notify_msg, level="info")
    
    return {
        "success": True,
        "order_id": order_id,
        "message": msg,
        "status": "SUBMITTED"
    }

def cancel_broker_order(order_id: str, portfolio_id: str = "default") -> bool:
    """
    撤销挂单的抽象接口
    """
    logging.info(f"[Broker API] 撤销委托单: {order_id} (组合: {portfolio_id})")
    return True
