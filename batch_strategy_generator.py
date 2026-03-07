#!/usr/bin/env python3
"""
批量生成持仓股票策略
为所有持仓股票运行蓝军军团策略生成
"""
import sys
import os
import json
import sqlite3
from datetime import datetime

# 添加路径
sys.path.insert(0, '/Users/zuliangzhao/MarketMonitorAndBuyer')

# 持仓股票列表 (更新为实际持仓)
HOLDINGS = ['588200']

def get_db_connection():
    """获取数据库连接"""
    db_path = '/Users/zuliangzhao/MarketMonitorAndBuyer/user_data.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_stock_position(symbol):
    """获取股票持仓"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM positions WHERE symbol = ?', (symbol,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    else:
        return {'symbol': symbol, 'shares': 0, 'cost': 0.0, 'base_shares': 0}

def get_stock_history(symbol):
    """获取股票交易历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM history WHERE symbol = ? ORDER BY timestamp', (symbol,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_strategy_log(symbol, timestamp, result, reasoning, tag="【盘前策略】"):
    """保存策略日志"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO strategy_logs 
        (symbol, timestamp, result, reasoning, prompt, tag, model)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, timestamp, result, reasoning, "批量盘前策略生成", tag, "DeepSeek-R1"))
    
    conn.commit()
    conn.close()

def run_batch_analysis():
    """运行批量分析"""
    print("=" * 70)
    print("📈 批量盘前策略生成系统")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 持仓标的: {', '.join(HOLDINGS)}")
    print("=" * 70)
    
    # 加载配置
    try:
        from utils.config import load_config
        config = load_config()
        settings = config.get('settings', {})
        
        deepseek_key = settings.get('deepseek_api_key')
        kimi_key = settings.get('kimi_api_key')
        qwen_key = settings.get('qwen_api_key')
        kimi_base_url = settings.get('kimi_base_url', 'https://api.moonshot.cn/v1')
        
        if not deepseek_key:
            print("❌ 缺少DeepSeek API密钥")
            return False
        if not kimi_key:
            print("❌ 缺少 Kimi API 密钥 (运行五步工作流必需)")
            return False
            
        print("✅ API密钥加载成功")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False
    
    results = []
    
    for symbol in HOLDINGS:
        print(f"\n{'='*70}")
        print(f"📊 分析标的: {symbol}")
        print(f"{'='*70}")
        
        try:
            # 获取实时数据
            print("1. 📥 获取实时数据...")
            from utils.data_fetcher import get_stock_realtime_info, get_stock_fund_flow
            
            info = get_stock_realtime_info(symbol)
            if not info:
                print(f"❌ 无法获取{symbol}的实时数据")
                continue
            
            print(f"   ✅ {info.get('name', symbol)} @ {info.get('price', 'N/A')}")
            
            # 获取持仓和历史
            print("2. 📊 获取持仓和历史数据...")
            position = get_stock_position(symbol)
            history = get_stock_history(symbol)
            fund_flow = get_stock_fund_flow(symbol)
            
            print(f"   ✅ 持仓: {position.get('shares', 0)}股 @ 成本{position.get('cost', 0):.3f}")
            
            # 运行五步工作流
            print("3. 🤖 运行蓝军军团策略生成...")
            from scripts.five_step_moe import run_five_step_workflow
            
            result = run_five_step_workflow(
                symbol=symbol,
                info=info,
                position=position,
                history=history,
                fund_flow=fund_flow,
                deepseek_api_key=deepseek_key,
                kimi_api_key=kimi_key,
                qwen_api_key=qwen_key,
                kimi_base_url=kimi_base_url,
                intel_hub_data=""
            )
            
            # 提取最终策略
            final_order = result.get('final_order', '无策略生成')
            reasoning = result.get('reasoning', '')
            
            # 保存策略日志
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            save_strategy_log(
                symbol=symbol,
                timestamp=timestamp,
                result=final_order,
                reasoning=json.dumps(reasoning, ensure_ascii=False) if reasoning else '',
                tag="【盘前策略】"
            )
            
            print(f"4. 💾 策略已保存到数据库")
            
            # 记录结果
            analysis_result = {
                'symbol': symbol,
                'timestamp': timestamp,
                'price': info.get('price'),
                'name': info.get('name'),
                'shares': position.get('shares', 0),
                'strategy_saved': True
            }
            results.append(analysis_result)
            
            # 显示策略摘要
            print("5. 📋 策略摘要:")
            print("-" * 40)
            if isinstance(final_order, str):
                lines = final_order.split('\n')
                for line in lines[:20]:
                    if any(keyword in line for keyword in ['方向', '建议', '买入', '卖出', '观望', '目标', '止损', '止盈', '仓位', '场景']):
                        print(f"   {line}")
            else:
                print(f"   {str(final_order)[:200]}...")
                
        except Exception as e:
            print(f"❌ {symbol}分析失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 生成摘要报告
    print("\n" + "=" * 70)
    print("📊 批量策略生成摘要")
    print("=" * 70)
    
    success_count = len([r for r in results if r.get('strategy_saved')])
    
    print(f"📈 总标的数: {len(HOLDINGS)}")
    print(f"✅ 成功生成: {success_count}")
    print(f"❌ 失败: {len(HOLDINGS) - success_count}")
    
    for result in results:
        print(f"\n  {result['symbol']} ({result.get('name', '')}):")
        print(f"    价格: {result.get('price', 'N/A')}")
        print(f"    持仓: {result.get('shares', 0)}股")
        print(f"    状态: {'✅ 已生成' if result.get('strategy_saved') else '❌ 失败'}")
    
    print("\n" + "=" * 70)
    print("🎉 所有持仓股票策略生成完成！")
    print("=" * 70)
    
    return success_count > 0

if __name__ == '__main__':
    success = run_batch_analysis()
    sys.exit(0 if success else 1)
