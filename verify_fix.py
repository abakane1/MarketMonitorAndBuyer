import sys
import os

# 将当前目录添加到路径中以导入 utils
sys.path.append(os.getcwd())

try:
    from utils.data_fetcher import get_stock_fund_flow
    import pandas as pd
    
    print("正在尝试获取股票 600519 的资金流向数据...")
    result = get_stock_fund_flow("600519")
    
    if "error" in result:
        print(f"获取失败: {result['error']}")
    else:
        print("获取成功!")
        print(result)
        
except NameError as e:
    print(f"验证失败: 捕获到 NameError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"发生其他错误: {e}")
    sys.exit(1)

print("验证通过！")
