#!/usr/bin/env python3
"""
Five-Step MoE (Mixture of Experts) Workflow
五步专家混合工作流 - 蓝军(DeepSeek-R1) + 红军(Qwen-Max)

Step 1: Draft    → DeepSeek-R1 (蓝军主帅初稿)
Step 2: Audit    → Qwen-Max    (红军审计)
Step 3: Refine   → DeepSeek-R1 (蓝军优化)
Step 4: Verdict  → Qwen-Max    (红军终审)
Step 5: Order    → DeepSeek-R1 (蓝军执行令)
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Union

# Import existing AI functions from utils.ai_advisor
from utils.ai_advisor import (
    call_deepseek_api,
    call_qwen_api,
    build_advisor_prompt,
    build_red_team_prompt,
    build_refinement_prompt,
    build_final_decision_prompt
)

# Import prompt loader
from utils.prompt_loader import load_all_prompts


def _load_prompt_templates() -> Dict[str, str]:
    """加载提示词模板"""
    try:
        return load_all_prompts()
    except Exception as e:
        print(f"⚠️ 提示词加载失败，使用默认模板: {e}")
        return {}


def step1_blue_draft(
    symbol: str,
    info: Dict,
    position: Dict,
    history: list,
    fund_flow: Dict,
    deepseek_api_key: str,
    prompt_templates: Optional[Dict] = None,
    intel_hub_data: str = "",
    minute_summary: str = ""
) -> Dict[str, Any]:
    """
    Step 1: 蓝军生成初始草案 (DeepSeek-R1)
    """
    print("\n🟦 STEP 1/5: 蓝军主帅生成初始策略草案...")
    print("   模型: DeepSeek-R1 (reasoner)")
    
    # 构建上下文数据
    current_price = info.get('price', 0)
    cost = position.get('cost', 0)
    shares = position.get('shares', 0)
    profit_pct = ((current_price - cost) / cost * 100) if cost > 0 else 0
    
    context_data = {
        'code': symbol,
        'name': info.get('name', symbol),
        'price': current_price,
        'pre_close': info.get('pre_close', current_price),
        'shares': shares,
        'cost': cost,
        'avg_cost': cost,
        'available_cash': position.get('available_cash', 0),
        'total_capital': position.get('total_capital', 500000),
        'capital_allocation': position.get('capital_allocation', 100000),
        'base_shares': position.get('base_shares', 0),
        'change_pct': info.get('change_pct', 0),
        'date': datetime.now().strftime('%Y-%m-%d'),
    }
    
    # 构建技术指标数据
    technical_indicators = {
        'daily_stats': f"现价: {current_price}, 成本: {cost}, 盈亏: {profit_pct:+.2f}%",
        'signal_summary': 'LAG+GTO策略分析',
    }
    
    # 构建提示词
    sys_prompt, user_prompt = build_advisor_prompt(
        context_data=context_data,
        research_context=intel_hub_data + "\n" + minute_summary,
        technical_indicators=technical_indicators,
        fund_flow_data=fund_flow,
        fund_flow_history=None,
        intraday_summary=None,
        prompt_templates=prompt_templates or _load_prompt_templates(),
        suffix_key="proposer_premarket_suffix",
        symbol=symbol
    )
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, sys_prompt, user_prompt)
    
    print(f"   ✅ 草案生成完成 ({len(content)} 字符)")
    if reasoning:
        print(f"   🧠 推理过程: {len(reasoning)} 字符")
    
    return {
        'step': 1,
        'role': '蓝军主帅 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'system_prompt': sys_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step2_red_audit(
    symbol: str,
    info: Dict,
    blue_draft: Dict,
    qwen_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 2: 红军审计蓝军草案 (Qwen-Max)
    """
    print("\n🟥 STEP 2/5: 红军审计师进行风险审查...")
    print("   模型: Qwen-Max")
    
    context_data = {
        'code': symbol,
        'name': info.get('name', symbol),
        'price': info.get('price', 0),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'daily_stats': f"当前价格: {info.get('price', 0)}",
        'deepseek_plan': blue_draft['content'],
    }
    
    sys_prompt, user_prompt = build_red_team_prompt(
        context_data=context_data,
        prompt_templates=prompt_templates or _load_prompt_templates(),
        is_final_round=False
    )
    
    # 调用 Qwen-Max
    content = call_qwen_api(qwen_api_key, sys_prompt, user_prompt, model="qwen-max")
    
    print(f"   ✅ 审计报告完成 ({len(content)} 字符)")
    
    return {
        'step': 2,
        'role': '红军审计 (Qwen-Max)',
        'content': content,
        'system_prompt': sys_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step3_blue_refinement(
    symbol: str,
    info: Dict,
    blue_draft: Dict,
    red_audit: Dict,
    deepseek_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 3: 蓝军根据审计意见优化策略 (DeepSeek-R1)
    """
    print("\n🟦 STEP 3/5: 蓝军主帅反思并优化策略...")
    print("   模型: DeepSeek-R1 (reasoner)")
    
    sys_prompt, user_prompt = build_refinement_prompt(
        original_context=blue_draft.get('user_prompt', ''),
        original_plan=blue_draft['content'],
        audit_report=red_audit['content'],
        prompt_templates=prompt_templates or _load_prompt_templates()
    )
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, sys_prompt, user_prompt)
    
    print(f"   ✅ 优化策略完成 ({len(content)} 字符)")
    if reasoning:
        print(f"   🧠 推理过程: {len(reasoning)} 字符")
    
    return {
        'step': 3,
        'role': '蓝军优化 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'system_prompt': sys_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step4_red_verdict(
    symbol: str,
    info: Dict,
    blue_refinement: Dict,
    qwen_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 4: 红军最终裁决 (Qwen-Max)
    """
    print("\n🟥 STEP 4/5: 红军进行最终裁决...")
    print("   模型: Qwen-Max")
    
    context_data = {
        'code': symbol,
        'name': info.get('name', symbol),
        'price': info.get('price', 0),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'daily_stats': f"当前价格: {info.get('price', 0)}",
        'deepseek_plan': blue_refinement['content'],
    }
    
    sys_prompt, user_prompt = build_red_team_prompt(
        context_data=context_data,
        prompt_templates=prompt_templates or _load_prompt_templates(),
        is_final_round=True  # 这是最终轮
    )
    
    # 调用 Qwen-Max
    content = call_qwen_api(qwen_api_key, sys_prompt, user_prompt, model="qwen-max")
    
    # 解析裁决结果
    decision = "待定"
    if "批准" in content or "通过" in content or "同意" in content:
        decision = "✅ 批准执行"
    elif "修正" in content or "修改" in content:
        decision = "⚠️ 建议修正"
    elif "驳回" in content or "否决" in content:
        decision = "❌ 驳回重做"
    
    print(f"   ✅ 最终裁决: {decision}")
    
    return {
        'step': 4,
        'role': '红军终审 (Qwen-Max)',
        'content': content,
        'decision': decision,
        'system_prompt': sys_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step5_blue_final_order(
    symbol: str,
    info: Dict,
    position: Dict,
    workflow_history: list,
    deepseek_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 5: 蓝军生成最终执行令 (DeepSeek-R1)
    """
    print("\n🟦 STEP 5/5: 蓝军主帅生成最终执行令...")
    print("   模型: DeepSeek-R1 (reasoner)")
    
    current_price = info.get('price', 0)
    cost = position.get('cost', 0)
    shares = position.get('shares', 0)
    profit_pct = ((current_price - cost) / cost * 100) if cost > 0 else 0
    
    context_data = {
        'code': symbol,
        'name': info.get('name', symbol),
        'price': current_price,
        'pre_close': info.get('pre_close', current_price),
        'shares': shares,
        'cost': cost,
        'change_pct': info.get('change_pct', 0),
    }
    
    # 聚合历史记录
    history_text = []
    for i, step in enumerate(workflow_history):
        history_text.append(f"【Step {i+1}: {step.get('role', 'Unknown')}】\n{step.get('content', '')}")
    
    sys_prompt, user_prompt = build_final_decision_prompt(
        aggregated_history=history_text,
        prompt_templates=prompt_templates or _load_prompt_templates(),
        context_data=context_data
    )
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, sys_prompt, user_prompt)
    
    print(f"   ✅ 执行令生成完成 ({len(content)} 字符)")
    
    return {
        'step': 5,
        'role': '蓝军执行 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'final_order': content,  # 别名，方便调用者使用
        'system_prompt': sys_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def run_five_step_workflow(
    symbol: str,
    info: Dict,
    position: Dict,
    history: list,
    fund_flow: Dict,
    deepseek_api_key: str,
    qwen_api_key: str,
    intel_hub_data: Union[str, Dict] = "",
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    运行完整的五步 MoE 工作流
    
    Args:
        symbol: 股票代码
        info: 实时行情数据
        position: 持仓数据
        history: 交易历史
        fund_flow: 资金流向数据
        deepseek_api_key: DeepSeek API Key
        qwen_api_key: Qwen API Key
        intel_hub_data: 情报库数据
        prompt_templates: 提示词模板
        
    Returns:
        Dict 包含所有步骤的结果
    """
    start_time = datetime.now()
    print("=" * 70)
    print("🚀 启动五步 MoE 分析工作流")
    print(f"   标的: {symbol} ({info.get('name', 'N/A')})")
    print(f"   当前价: {info.get('price', 0)}")
    print("=" * 70)
    
    # 加载提示词模板
    if prompt_templates is None:
        prompt_templates = _load_prompt_templates()
    
    # 准备分钟数据摘要
    minute_summary = ""  # 如果需要，可以从外部传入
    
    results = {}
    workflow_history = []
    
    try:
        # Step 1: 蓝军初稿
        results['draft'] = step1_blue_draft(
            symbol=symbol,
            info=info,
            position=position,
            history=history,
            fund_flow=fund_flow,
            deepseek_api_key=deepseek_api_key,
            prompt_templates=prompt_templates,
            intel_hub_data=intel_hub_data,
            minute_summary=minute_summary
        )
        workflow_history.append(results['draft'])
        
        # Step 2: 红军审计
        results['audit'] = step2_red_audit(
            symbol=symbol,
            info=info,
            blue_draft=results['draft'],
            qwen_api_key=qwen_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['audit'])
        
        # Step 3: 蓝军优化
        results['refined'] = step3_blue_refinement(
            symbol=symbol,
            info=info,
            blue_draft=results['draft'],
            red_audit=results['audit'],
            deepseek_api_key=deepseek_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['refined'])
        
        # Step 4: 红军终审
        results['verdict'] = step4_red_verdict(
            symbol=symbol,
            info=info,
            blue_refinement=results['refined'],
            qwen_api_key=qwen_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['verdict'])
        
        # Step 5: 最终执行令
        results['final'] = step5_blue_final_order(
            symbol=symbol,
            info=info,
            position=position,
            workflow_history=workflow_history,
            deepseek_api_key=deepseek_api_key,
            prompt_templates=prompt_templates
        )
        
        # 添加元数据
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        results['metadata'] = {
            'symbol': symbol,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'steps_completed': 5,
            'models_used': {
                'blue_team': 'DeepSeek-R1 (reasoner)',
                'red_team': 'Qwen-Max'
            }
        }
        
        # 添加最终执行令的便捷引用
        results['final_order'] = results['final']['final_order']
        
        print("\n" + "=" * 70)
        print(f"✅ 五步 MoE 工作流完成! 总耗时: {duration:.1f} 秒")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        results['error'] = str(e)
        results['metadata'] = {
            'symbol': symbol,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'error': str(e)
        }
    
    return results


# 简单测试
if __name__ == "__main__":
    print("五步 MoE 工作流模块加载成功")
    print("用法: from scripts.five_step_moe import run_five_step_workflow")
