#!/usr/bin/env python3
"""
全自动策略生成系统
- 使用系统内5步MoE工作流
- 使用千问(Kimi)作为蓝军主模型
- 保存到review_logs表(系统可见)
- 每天收盘后自动运行
"""
import sys
import os
import json
from datetime import datetime

# 添加路径
sys.path.insert(0, '/Users/zuliangzhao/MarketMonitorAndBuyer')

def get_watchlist_symbols():
    """从关注列表获取股票代码"""
    from utils.database import db_get_watchlist_with_names
    watchlist = db_get_watchlist_with_names()
    # 过滤出ETF代码(以5开头)
    etf_symbols = [symbol for symbol, name in watchlist if symbol.startswith('5')]
    return etf_symbols

def get_stock_position(symbol):
    """获取股票持仓"""
    from utils.database import db_get_position
    return db_get_position(symbol)

def run_auto_strategy_generation():
    """运行全自动策略生成"""
    print("=" * 70)
    print("🤖 全自动策略生成系统 (Auto-Drive Mode)")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 加载配置和API密钥
    try:
        from utils.config import load_config
        config = load_config()
        settings = config.get('settings', {})
        
        # 使用千问/Kimi作为主模型(蓝军)
        qwen_key = settings.get('qwen_api_key') or settings.get('kimi_api_key')
        # DeepSeek作为审计模型(红军)
        deepseek_key = settings.get('deepseek_api_key')
        
        if not qwen_key:
            print("❌ 缺少Qwen/Kimi API密钥")
            return False
        if not deepseek_key:
            print("❌ 缺少DeepSeek API密钥")
            return False
            
        print("✅ API密钥加载成功")
        print(f"   蓝军(主模型): Kimi/Qwen")
        print(f"   红军(审计): DeepSeek")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False
    
    # 2. 获取关注列表
    print("\n📋 获取关注列表...")
    symbols = get_watchlist_symbols()
    if not symbols:
        print("❌ 关注列表为空")
        return False
    print(f"   找到 {len(symbols)} 只ETF: {', '.join(symbols)}")
    
    # 3. 为每只ETF生成策略
    results = []
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"📊 生成策略: {symbol}")
        print(f"{'='*70}")
        
        try:
            # 获取实时数据
            print("1. 📥 获取实时数据...")
            from utils.data_fetcher import get_stock_realtime_info, get_stock_fund_flow
            from utils.database import db_get_history
            
            info = get_stock_realtime_info(symbol)
            if not info:
                print(f"   ❌ 无法获取{symbol}的实时数据")
                continue
            print(f"   ✅ {info.get('name', symbol)} @ {info.get('price', 'N/A')}")
            
            # 获取持仓和历史
            print("2. 📊 获取持仓和历史...")
            position = get_stock_position(symbol)
            history = db_get_history(symbol)
            fund_flow = get_stock_fund_flow(symbol)
            print(f"   ✅ 持仓: {position.get('shares', 0)}股 @ 成本{position.get('cost', 0):.3f}")
            
            # 运行5步MoE工作流 (使用系统内部逻辑)
            print("3. 🤖 运行5步MoE工作流...")
            print("   Step 1/5: 蓝军(Kimi)生成初始草案...")
            print("   Step 2/5: 红军(DeepSeek)初审...")
            print("   Step 3/5: 蓝军(Kimi)反思优化...")
            print("   Step 4/5: 红军(DeepSeek)终审...")
            print("   Step 5/5: 蓝军签署执行令...")
            
            from scripts.five_step_moe import run_five_step_workflow
            
            result = run_five_step_workflow(
                symbol=symbol,
                info=info,
                position=position,
                history=history,
                fund_flow=fund_flow,
                deepseek_api_key=qwen_key,  # 蓝军=Kimi
                qwen_api_key=deepseek_key,   # 红军=DeepSeek
                intel_hub_data=""
            )
            
            final_order = result.get('final_order', '无策略生成')
            
            # 构建完整的策略结果（包含所有步骤）
            full_result = f"""# 🎯 最终执行令 (Final Order)
{final_order}

---

# 📜 完整工作流记录

## 🟦 Step 1: 蓝军初稿 (Kimi)
{result.get('draft', {}).get('content', 'N/A')}

---

## 🟥 Step 2: 红军初审 (DeepSeek-R1)
{result.get('audit', {}).get('content', 'N/A')}

---

## 🟦 Step 3: 蓝军优化 (Kimi)
{result.get('refined', {}).get('content', 'N/A')}

---

## 🟥 Step 4: 红军终审 (DeepSeek-R1)
**裁决**: {result.get('verdict', {}).get('decision', 'N/A')}

{result.get('verdict', {}).get('content', 'N/A')}

---

## 🟦 Step 5: 最终执行令 (Kimi)
{result.get('final', {}).get('content', 'N/A')}
"""
            
            # 提取推理过程
            reasoning = result.get('final', {}).get('reasoning', '')
            if not reasoning:
                reasoning = result.get('draft', {}).get('reasoning', '')
            
            # 构建完整的提示词历史
            draft = result.get('draft', {})
            audit = result.get('audit', {})
            refined = result.get('refined', {})
            verdict = result.get('verdict', {})
            final = result.get('final', {})
            
            full_prompt_log = f"""# 🧠 提示词历史 (Prompts History)

## Step 1: 蓝军初稿
### System
{draft.get('system_prompt', 'N/A')[:500]}...

### User  
{draft.get('user_prompt', 'N/A')[:500]}...

---

## Step 2: 红军初审
### System
{audit.get('system_prompt', 'N/A')[:500]}...

### User
{audit.get('user_prompt', 'N/A')[:500]}...

---

## Step 3: 蓝军优化
### System
{refined.get('system_prompt', 'N/A')[:500]}...

### User
{refined.get('user_prompt', 'N/A')[:500]}...

---

## Step 4: 红军终审
### System
{verdict.get('system_prompt', 'N/A')[:500]}...

### User
{verdict.get('user_prompt', 'N/A')[:500]}...

---

## Step 5: 最终执行令
### System
{final.get('system_prompt', 'N/A')[:500]}...

### User
{final.get('user_prompt', 'N/A')[:500]}...
"""
            
            # 4. 保存到review_logs表(系统内可见)
            print("4. 💾 保存完整工作流到系统数据库(review_logs)...")
            from utils.storage import save_production_log
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建details包含完整的prompts_history
            prompts_history = {
                'draft_sys': draft.get('system_prompt', ''),
                'draft_user': draft.get('user_prompt', ''),
                'audit1_sys': audit.get('system_prompt', ''),
                'audit1_user': audit.get('user_prompt', ''),
                'refine_sys': refined.get('system_prompt', ''),
                'refine_user': refined.get('user_prompt', ''),
                'final_sys': verdict.get('system_prompt', ''),
                'final_user': verdict.get('user_prompt', '')
            }
            
            save_production_log(
                symbol=symbol,
                prompt=full_prompt_log,
                result=full_result,
                reasoning=reasoning if reasoning else "5步MoE工作流自动生成",
                model="Kimi-DeepSeek-MoE",  # 蓝军=Kimi, 红军=DeepSeek
                details=json.dumps({
                    'auto_generated': True,
                    'blue_team': 'Kimi',  # 修正: 蓝军是Kimi
                    'red_team': 'DeepSeek',  # 修正: 红军是DeepSeek
                    'steps': 5,
                    'price': info.get('price'),
                    'shares': position.get('shares', 0),
                    'prompts_history': prompts_history,
                    'metadata': result.get('metadata', {})
                }, ensure_ascii=False)
            )
            
            print(f"   ✅ 已保存完整工作流到review_logs表 ({len(full_result)} 字符)")
            
            results.append({
                'symbol': symbol,
                'success': True,
                'timestamp': timestamp
            })
            
        except Exception as e:
            print(f"   ❌ 生成失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'symbol': symbol,
                'success': False,
                'error': str(e)
            })
    
    # 5. 生成摘要
    print("\n" + "=" * 70)
    print("📊 生成摘要")
    print("=" * 70)
    
    success_count = sum(1 for r in results if r['success'])
    print(f"✅ 成功: {success_count}/{len(symbols)}")
    
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"   {status} {r['symbol']}")
    
    print("\n" + "=" * 70)
    print("🎉 全自动策略生成完成！")
    print("📱 明早08:30自动推送到飞书群")
    print("=" * 70)
    
    return success_count > 0

if __name__ == '__main__':
    success = run_auto_strategy_generation()
    sys.exit(0 if success else 1)