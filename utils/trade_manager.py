from utils.database import (
    db_get_position,
    db_update_position,
    db_add_history,
    db_get_all_positions
)
from datetime import datetime

def execute_trade(symbol: str, action: str, price: float, quantity: int, note: str = "快速交易") -> dict:
    """
    Executes a trade (Buy/Sell), updates position and history.
    
    Args:
        symbol: Stock code
        action: "buy" or "sell"
        price: Transaction price
        quantity: Transaction quantity (shares)
        note: Optional note
        
    Returns:
        dict: {
            "success": bool,
            "message": str,
            "new_position": dict (shares, cost)
        }
    """
    try:
        # 1. Fetch current position
        pos = db_get_position(symbol)
        current_shares = pos["shares"]
        current_cost = pos["cost"]
        base_shares = pos["base_shares"]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 2. Calculate Updates
        if action == "buy":
            new_shares = current_shares + quantity
            # Current Total Cost = current_shares * current_cost (Unit Cost)
            current_total_cost = current_shares * current_cost
            new_total_cost = current_total_cost + (price * quantity)
            
            new_shares = current_shares + quantity
            new_cost = new_total_cost / new_shares if new_shares > 0 else 0.0
            
            # Log
            db_add_history(symbol, timestamp, "买入", price, quantity, note)
            
        elif action == "sell":
            if current_shares < quantity:
                return {
                    "success": False,
                    "message": f"持仓不足: 当前 {current_shares}, 卖出 {quantity}"
                }
            
            # [MODIFIED] Diluted Cost Logic (摊薄成本法)
            # User Request: "Selling should reduce cost".
            # New Total Cost = Current Total Cost - (Sell Quantity * Sell Price)
            # This means we deduct the entire revenue from the cost basis.
            
            current_total_cost = current_shares * current_cost
            sell_revenue = quantity * price
            new_total_cost = current_total_cost - sell_revenue
            
            new_shares = current_shares - quantity
            
            if new_shares > 0:
                new_unit_cost = new_total_cost / new_shares
            else:
                new_unit_cost = 0.0 # Cleared position
                
            new_cost = new_unit_cost
            
            # Log
            db_add_history(symbol, timestamp, "卖出", price, quantity, note)

        else:
             return {"success": False, "message": f"无效动作: {action}"}
             
        # 3. Update Database
        db_update_position(symbol, new_shares, new_cost, base_shares)
        
        return {
            "success": True,
            "message": f"交易成功: {action.upper()} {quantity}股 @ {price}",
            "new_position": {"shares": new_shares, "cost": new_cost}
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"交易执行失败: {str(e)}"
        }
