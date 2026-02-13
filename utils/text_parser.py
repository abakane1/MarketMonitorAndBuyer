import re

def parse_trade_command(text: str) -> dict:
    """
    Parses a natural language trade command.
    
    Expected patterns:
    "600076 4.5 买入 1000"
    "600076 4.5 buy 1000"
    
    Returns:
        dict: {
            "symbol": str,
            "price": float,
            "quantity": int,
            "action": str ("buy" or "sell"),
            "valid": bool,
            "error": str (optional)
        }
    """
    text = text.strip()
    result = {
        "symbol": None,
        "price": None,
        "quantity": None,
        "action": None,
        "valid": False,
        "error": None
    }
    
    # 1. Extract Symbol (6 digits)
    symbol_match = re.search(r'\b(\d{6})\b', text)
    if not symbol_match:
        result["error"] = "未能识别有效的6位股票代码"
        return result
    result["symbol"] = symbol_match.group(1)
    
    # Remove symbol from text to avoid confusion with quantity
    text_no_symbol = text.replace(result["symbol"], "", 1)
    
    # 2. Extract Action
    if any(k in text for k in ["买", "buy", "入", "Buy", "in"]):
        result["action"] = "buy"
    elif any(k in text for k in ["卖", "sell", "出", "Sell", "out"]):
        result["action"] = "sell"
    else:
        result["error"] = "未能识别交易方向 (买/卖)"
        return result
        
    # 3. Extract Price and Quantity
    # Strategy: Find all numbers (float or int)
    # Usually: Price is float (has dot) or small int (< 200?), Quantity is large int (>= 100).
    # This is heuristic and might be tricky for high priced stocks (e.g. Maotai ~1700).
    # Better approach: Regex for float matching
    
    numbers = re.findall(r'\d+(?:\.\d+)?', text_no_symbol)
    
    # Filter out empty strings
    numbers = [n for n in numbers if n.strip()]
    
    if len(numbers) < 2:
         result["error"] = "未能识别价格和数量 (需包含两个数值)"
         return result
         
    # Heuristic: 
    # If one has ".", it's price.
    # If both are ints: The one > 1000 or multiple of 100 is likely quantity?
    # Or rely on order? (Price then Quantity OR Quantity then Price).
    # Let's assume standard input: Code Price Quantity
    
    v1 = float(numbers[0])
    v2 = float(numbers[1])
    
    price = None
    qty = None
    
    # Case A: Explicit decimal point
    if "." in numbers[0] and "." not in numbers[1]:
        price = v1
        qty = v2
    elif "." not in numbers[0] and "." in numbers[1]:
        qty = v1
        price = v2
    else:
        # Both ints or both floats (unlikely for qty).
        # Assume Qty is significantly larger or is a multiple of 100 multiple?
        # Or Price usually < 1000 (except Maotai) and Qty >= 100.
        # But this is ambiguous.
        # Let's check for keywords "股" for quantity, "元" for price
        
        # Re-parse with context if possible?
        # Let's stick to common sense: Price is usually smaller than Quantity *unless* buying 1 hand of Maotai.
        # A safer bet for "Code Price Qty" flow.
        pass

    # Keyword assisted extraction from parsing logic
    # Try looking for "X元" or "Xok" or "X股"
    
    # "10.5元"
    price_match = re.search(r'(\d+(?:\.\d+)?)\s*[元块]', text_no_symbol)
    if price_match:
        price = float(price_match.group(1))

    # "1000股"
    qty_match = re.search(r'(\d+)\s*[股手]', text_no_symbol)
    if qty_match:
        val = int(qty_match.group(1))
        # if '手', multiply by 100
        if '手' in text_no_symbol:
            qty = val * 100
        else:
            qty = val
            
    # If still None, map from v1/v2 based on heuristic
    if price is None and qty is None:
        # Simple heuristic: The smaller one is price (risky?)
        # Better: First number is price, second is qty (Standard convention)
        price = v1
        qty = v2
    elif price is None and qty is not None:
        # Find the other number from v1, v2
        price = v1 if v2 == qty else v2
    elif qty is None and price is not None:
        qty = v1 if v2 == price else v2
        
    result["price"] = price
    result["quantity"] = int(qty)
    
    if result["quantity"] <= 0:
        result["error"] = "数量必须大于0"
        return result
        
    if result["price"] <= 0:
        result["error"] = "价格必须大于0"
        return result
        
    result["valid"] = True
    return result
