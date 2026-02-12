#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.8.0 修复验证脚本

运行此脚本验证以下修复是否正常工作：
1. 备用数据源（新浪财经/腾讯财经）
2. 资金流向数据实时更新
3. 提示词 Markdown 加载
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_data_fallback():
    """测试备用数据源"""
    print("=== 测试备用数据源 ===")
    from utils.data_fallback import get_stock_spot_sina, get_stock_spot_tencent
    
    symbol = '600076'
    
    # Test Sina
    sina = get_stock_spot_sina(symbol)
    if sina:
        print(f"✅ 新浪财经: {sina['名称']} @ {sina['最新价']}")
    else:
        print("❌ 新浪财经: 获取失败")
    
    # Test Tencent
    tencent = get_stock_spot_tencent(symbol)
    if tencent:
        print(f"✅ 腾讯财经: {tencent['名称']} @ {tencent['最新价']}")
    else:
        print("❌ 腾讯财经: 获取失败")
    
    return sina is not None or tencent is not None


def test_fund_flow():
    """测试资金流向数据"""
    print("\n=== 测试资金流向数据 ===")
    from utils.data_fetcher import get_stock_fund_flow, get_stock_realtime_info
    
    symbol = '600076'
    
    # Get fund flow
    flow = get_stock_fund_flow(symbol)
    if flow and not flow.get('error'):
        print(f"✅ 资金流向获取成功")
        print(f"   最新价: {flow['最新价']}")
        print(f"   涨跌幅: {flow['涨跌幅']}")
        print(f"   数据来源: {flow.get('数据来源', '未知')}")
        
        # Verify data source
        if '实时' in flow.get('数据来源', ''):
            print("✅ 使用了实时数据源")
            return True
        else:
            print("⚠️ 未使用实时数据源")
            return False
    else:
        print(f"❌ 资金流向获取失败: {flow.get('error', '未知错误')}")
        return False


def test_prompt_loader():
    """测试提示词加载器"""
    print("\n=== 测试提示词加载器 ===")
    from utils.prompt_loader import load_all_prompts, load_prompt
    
    # Test loading all prompts
    prompts = load_all_prompts()
    if len(prompts) > 0:
        print(f"✅ 成功加载 {len(prompts)} 个提示词")
    else:
        print("❌ 未能加载提示词")
        return False
    
    # Test loading specific prompt
    try:
        system_prompt = load_prompt('system', 'proposer_system.md')
        if len(system_prompt) > 0:
            print("✅ 成功加载单个提示词文件")
            return True
        else:
            print("❌ 提示词文件为空")
            return False
    except Exception as e:
        print(f"❌ 加载提示词失败: {e}")
        return False


def main():
    print("MarketMonitorAndBuyer v2.8.0 修复验证\n")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(("备用数据源", test_data_fallback()))
    results.append(("资金流向数据", test_fund_flow()))
    results.append(("提示词加载器", test_prompt_loader()))
    
    # Summary
    print("\n" + "=" * 50)
    print("验证结果汇总:")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 所有测试通过！v2.8.0 修复正常工作。")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
