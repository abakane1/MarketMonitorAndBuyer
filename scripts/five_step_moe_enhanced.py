#!/usr/bin/env python3
"""
Enhanced Five-Step MoE (Mixture of Experts) Workflow - Deep Analysis Edition
深度研判升级版 - 整合技术面、基本面、情报面、资金面四维分析

核心升级:
1. 全面数据整合 (技术/基本面/情报/资金/历史)
2. 深度基本面分析 (财务、行业、催化剂)
3. 主力意图识别与资金流向解读
4. 市场情绪量化与情报权重评估
5. 历史策略复盘学习
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

# Import existing AI functions
from utils.ai_advisor import (
    call_deepseek_api,
    call_qwen_api,
    build_advisor_prompt,
    build_red_team_prompt,
    build_refinement_prompt,
    build_final_decision_prompt
)
from utils.prompt_loader import load_all_prompts

# Import enhanced data integrator
from scripts.data_integrator import DataIntegrator, format_enriched_context


def _load_prompt_templates() -> Dict[str, str]:
    """加载提示词模板"""
    try:
        return load_all_prompts()
    except Exception as e:
        print(f"⚠️ 提示词加载失败，使用默认模板: {e}")
        return {}


def step1_blue_draft_enhanced(
    symbol: str,
    info: Dict,
    position: Dict,
    history: list,
    fund_flow: Dict,
    deepseek_api_key: str,
    enriched_data: Dict[str, Any],
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 1: 蓝军生成深度分析初稿 (DeepSeek-R1)
    整合四维数据进行综合分析
    """
    print("\n🟦 STEP 1/5: 蓝军主帅深度分析 - 生成初始策略草案...")
    print("   模型: DeepSeek-R1 (reasoner)")
    print("   数据维度: 技术 | 基本面 | 资金面 | 情报")
    
    # 构建增强版上下文
    current_price = info.get('price', 0)
    cost = position.get('cost', 0)
    shares = position.get('shares', 0)
    profit_pct = ((current_price - cost) / cost * 100) if cost > 0 else 0
    
    # 格式化富化数据
    enriched_context = format_enriched_context(enriched_data)
    
    # 构建系统提示词 - 强调深度分析
    system_prompt = """你是[A股德州扑克 LAG + GTO 交易专家]，拥有20年经验。

【交易哲学: LAG + GTO】
1. **松凶 (LAG)**: 赔率有利时打法奔放；一旦锁定趋势则暴力进攻。
2. **GTO (博弈论最优)**: 混合"价值注"和"诈唬"，让市场无法预测。
3. **博弈思维**: 每笔交易都是下注。仅在 胜率 * 赔率 > 1 时入场。
4. **反人性心态**: 别人恐惧我贪婪，别人贪婪我恐惧。

【深度分析要求】
你必须综合分析以下四个维度，给出超越单纯技术面的深度研判：

1. **技术面**: 价格行为、支撑阻力、趋势判断
2. **基本面**: 财务健康度、行业地位、催化剂与风险
3. **资金面**: 主力意图识别、资金流向解读、筹码分布
4. **情报面**: 关键新闻影响、市场情绪、预期差分析

【输出要求】
- 必须引用具体数据支撑你的观点
- 必须分析主力资金的真实意图（吸筹/出货/洗盘）
- 必须评估基本面的风险与机会
- 必须给出明确的场景化交易计划
"""
    
    # 构建用户提示词
    user_prompt = f"""【深度分析任务】标的: {symbol} ({info.get('name', symbol)})

{enriched_context}

【持仓现状】
- 当前价格: {current_price}
- 持仓成本: {cost}
- 持仓数量: {shares:,}股
- 浮动盈亏: {profit_pct:+.2f}%

【分析要求】
请基于上述四维数据，进行深度研判：

1. **主力意图深度解读**
   - 分析主力资金的流入/流出背后的真实意图
   - 结合价格行为判断是吸筹、洗盘还是出货
   - 评估筹码分布和对手盘情况

2. **基本面风险评估**
   - 公司财务健康状况（营收、利润、负债）
   - 行业环境与竞争格局
   - 关键催化剂与潜在风险点

3. **市场情绪与预期差**
   - 当前市场情绪是贪婪还是恐惧？
   - 是否存在预期差（市场未充分定价的信息）？
   - 情报库中的关键信息如何影响决策？

4. **场景化交易策略**
   - 基于不同市场场景给出具体操作计划
   - 明确入场价位、止损位、止盈位、仓位建议
   - 说明每个场景的触发条件和应对逻辑

请在回复最后输出【决策摘要】：
方向: [买入/卖出/观望]
交易模式: [低吸/追涨]
量能条件: [无/放量]
建议价格: [具体价格]
建议股数: [具体数量]
止损价格: [具体价格]
止盈价格: [具体价格]
"""
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, system_prompt, user_prompt)
    
    print(f"   ✅ 深度分析草案完成 ({len(content)} 字符)")
    if reasoning:
        print(f"   🧠 推理过程: {len(reasoning)} 字符")
    
    return {
        'step': 1,
        'role': '蓝军主帅 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'enriched_data_summary': {
            'technical': enriched_data.get('technical', {}).get('data_available', False),
            'fundamental': enriched_data.get('fundamental', {}).get('data_available', False),
            'fund_flow': enriched_data.get('fund_flow', {}).get('data_available', False),
            'intelligence': enriched_data.get('intelligence', {}).get('data_available', False)
        },
        'timestamp': datetime.now().isoformat()
    }


def step2_red_audit_enhanced(
    symbol: str,
    info: Dict,
    blue_draft: Dict,
    enriched_data: Dict[str, Any],
    qwen_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 2: 红军审计 - 深度风险评估 (Qwen-Max)
    """
    print("\n🟥 STEP 2/5: 红军审计师进行深度风险审查...")
    print("   模型: Qwen-Max")
    
    # 获取基本面风险信息
    fundamental = enriched_data.get('fundamental', {})
    risks = fundamental.get('risk_factors', [])
    
    system_prompt = """你是一位拥有20年经验的【A股德州扑克 LAG + GTO 交易专家】。
你现在担任【策略审计师】(Auditor)，你的交易哲学与蓝军完全一致：LAG (松凶) + GTO (博弈论最优)。

你的职责是进行【一致性审查】与【深度风险评估】：

1. **数据真实性核查**: 蓝军引用的数据是否真实存在？是否基于事实？

2. **主力意图判断审核**: 
   - 蓝军对主力意图的解读是否合理？
   - 是否有证据支持其判断（吸筹/出货/洗盘）？
   - 是否存在过度解读或一厢情愿？

3. **基本面风险评估**:
   - 蓝军是否充分考虑了基本面风险？
   - 财务风险、行业风险、政策风险是否被低估？
   - 催化剂的可实现性如何？

4. **LAG/GTO 体系评估**: 
   - 蓝军的决策是否符合 LAG + GTO 体系？
   - 进攻性检查：是否足够果断？
   - 赔率检查：GTO 视角下，这笔交易的 EV 是否为正？

5. **情报利用评估**:
   - 蓝军是否充分使用了情报库的信息？
   - 关键情报是否被正确解读和影响决策？

目标：确保蓝军的策略是该体系下的**最优解**，且风险可控。
"""
    
    user_prompt = f"""【审计上下文】
交易日期: {datetime.now().strftime('%Y-%m-%d')}
标的: {symbol} ({info.get('name', symbol)})
当前价格: {info.get('price', 0)}

【蓝军深度分析方案 (待审查)】
{blue_draft['content']}

【基本面风险清单】
{chr(10).join(['• ' + r[:100] for r in risks[:5]]) if risks else '• 未发现明确风险记录'}

【审计任务】
请以【LAG + GTO 专家】的身份对上述深度分析进行同行评审 (Peer Review)。

【输出格式】
1. **数据真实性核查**: 
   - 蓝军是否捏造了数据？(通过/未通过)

2. **主力意图判断审核**:
   - 蓝军对主力意图的解读是否合理？(合理/过度解读/证据不足)
   - 请说明理由

3. **基本面风险评估**: 
   - 蓝军是否充分考虑了财务风险？(充分/不充分)
   - 催化剂的可实现性评估？(高/中/低)

4. **LAG/GTO 体系评估**: 
   - 进攻欲望是否匹配当前牌面？(是/否, 理由)
   - 赔率计算是否合理？

5. **情报利用评估**:
   - 蓝军是否充分使用了情报信息？(充分/不充分)
   - 关键情报是否被正确解读？

6. **专家最终裁决**: (批准执行 / 建议修正 / 驳回重做)
   - *如果是建议修正，请给出具体的 GTO 调整建议。*
"""
    
    # 调用 Qwen-Max
    content = call_qwen_api(qwen_api_key, system_prompt, user_prompt, model="qwen-max")
    
    print(f"   ✅ 深度审计报告完成 ({len(content)} 字符)")
    
    return {
        'step': 2,
        'role': '红军审计 (Qwen-Max)',
        'content': content,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step3_blue_refinement_enhanced(
    symbol: str,
    info: Dict,
    blue_draft: Dict,
    red_audit: Dict,
    enriched_data: Dict[str, Any],
    deepseek_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 3: 蓝军根据审计意见优化策略 (DeepSeek-R1)
    """
    print("\n🟦 STEP 3/5: 蓝军主帅根据审计意见深度优化策略...")
    print("   模型: DeepSeek-R1 (reasoner)")
    
    # 获取历史策略用于复盘学习
    strategy_history = enriched_data.get('strategy_history', [])
    
    system_prompt = """你是[A股德州扑克 LAG + GTO 交易专家]。

你现在需要根据红军审计师的反馈，深度优化你的交易策略。

【优化要求】
1. 如果红军指出了数据或逻辑错误，必须修正
2. 如果红军质疑主力意图判断，必须提供更充分的证据或调整判断
3. 如果红军指出基本面风险考虑不足，必须补充风险分析
4. 如果红军认为赔率计算不合理，必须重新计算并调整

【历史学习】
参考过去类似情况下的策略表现，避免重复犯错。

【输出要求】
输出优化后的完整策略方案，明确说明做了哪些关键修正。
"""
    
    # 构建历史复盘上下文
    history_context = ""
    if strategy_history:
        history_context = "\n【历史策略复盘参考】\n"
        for i, strat in enumerate(strategy_history[-3:], 1):
            date = strat.get('date', 'N/A')
            advice = strat.get('advice', '')[:300]
            history_context += f"\n历史策略 {i} ({date}):\n{advice}...\n"
    
    user_prompt = f"""【策略优化任务】

【红军审计意见】
{red_audit['content']}

【我的原始分析】
{blue_draft['content']}
{history_context}

【优化要求】
请基于红军审计意见，对原策略进行深度优化：

1. **修正错误**: 如果有数据或逻辑错误，请明确修正
2. **补充风险分析**: 如果风险考虑不足，请补充基本面风险评估
3. **调整主力判断**: 如果主力意图判断被质疑，请提供更充分的论证或调整
4. **优化赔率计算**: 重新评估风险收益比，调整入场/止损/止盈位
5. **完善场景应对**: 针对更多可能的市场场景给出应对预案

请输出优化后的【指挥官 v2.0 最终决策摘要】，并说明关键修正点。
"""
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, system_prompt, user_prompt)
    
    print(f"   ✅ 深度优化策略完成 ({len(content)} 字符)")
    
    return {
        'step': 3,
        'role': '蓝军优化 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step4_red_verdict_enhanced(
    symbol: str,
    info: Dict,
    blue_refinement: Dict,
    enriched_data: Dict[str, Any],
    qwen_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Step 4: 红军最终裁决 (Qwen-Max)
    """
    print("\n🟥 STEP 4/5: 红军进行最终裁决...")
    print("   模型: Qwen-Max")
    
    # 获取情绪数据
    sentiment = enriched_data.get('market_sentiment', {})
    
    system_prompt = """你是【策略终审官】(Final Auditor)。

这是蓝军修正后的 v2.0 版本。请进行最终审查：

【终审重点】
1. 之前的隐患是否已消除？
2. 基本面风险是否已充分考虑？
3. 主力意图判断是否已有充分证据支持？
4. 策略是否具备可执行性？

如果核心问题已解决，请批准执行；否则请驳回。
"""
    
    user_prompt = f"""【最终裁决任务】

【市场情绪背景】
整体情绪: {sentiment.get('overall', '未知')}
主力态度: {sentiment.get('main_force_attitude', '未知')}
散户情绪: {sentiment.get('retail_attitude', '未知')}

【蓝军 v2.0 优化方案】
{blue_refinement['content']}

【终审问题】
1. 红军初审提出的问题是否已解决？
2. 基本面风险是否已充分纳入考量？
3. 主力意图判断是否有充分证据？
4. 策略的可执行性如何？

【输出格式】
- 风险评级: [低/中/高]
- 关键隐患: [无/列出隐患]
- 最终结论: [Approved/建议修正/驳回重做]
- 终审意见: [详细说明]
"""
    
    # 调用 Qwen-Max
    content = call_qwen_api(qwen_api_key, system_prompt, user_prompt, model="qwen-max")
    
    # 解析裁决结果
    decision = "待定"
    if "Approved" in content or "批准" in content or "通过" in content:
        decision = "✅ 批准执行"
    elif "修正" in content or "修改" in content:
        decision = "⚠️ 建议修正"
    elif "驳回" in content or "重做" in content:
        decision = "❌ 驳回重做"
    
    print(f"   ✅ 最终裁决: {decision}")
    
    return {
        'step': 4,
        'role': '红军终审 (Qwen-Max)',
        'content': content,
        'decision': decision,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def step5_blue_final_order_enhanced(
    symbol: str,
    info: Dict,
    position: Dict,
    workflow_history: list,
    enriched_data: Dict[str, Any],
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
    
    system_prompt = """你是[A股德州扑克 LAG + GTO 交易专家]。

基于前五步的博弈过程，生成简洁明确的最终执行令。

【执行令要求】
1. 必须是可立即执行的具体指令
2. 必须包含明确的场景触发条件
3. 必须包含具体的价位和股数
4. 必须包含风险控制措施

【风格】
简洁、果断、可执行。像军事命令一样清晰。
"""
    
    # 聚合历史记录
    history_text = []
    for i, step in enumerate(workflow_history):
        history_text.append(f"【Step {i+1}: {step.get('role', 'Unknown')}】\n{step.get('content', '')}")
    
    user_prompt = f"""【最终决策任务】

【博弈历史】
{chr(10).join(history_text)}

【当前状态】
标的: {symbol} ({info.get('name', symbol)})
最新价: {current_price}
持仓: {shares:,}股 @ {cost}

【输出要求】
生成最终执行令，格式如下：

[决策] 执行/观望/减仓/清仓
[标的] {symbol} / {info.get('name', symbol)}

【场景演练与挂单指令】

**场景 A: [场景描述]**
- [方向] 买入/卖出
- [触发条件] [具体条件]
- [建议价格] [价格区间]
- [建议股数] [数量]
- [止损] [止损位]

**场景 B: [场景描述]**
...

**场景 C: [极端风控]**
...

【指挥官寄语】[一句话总结核心思想]
"""
    
    # 调用 DeepSeek-R1
    content, reasoning = call_deepseek_api(deepseek_api_key, system_prompt, user_prompt)
    
    print(f"   ✅ 执行令生成完成 ({len(content)} 字符)")
    
    return {
        'step': 5,
        'role': '蓝军执行 (DeepSeek-R1)',
        'content': content,
        'reasoning': reasoning,
        'final_order': content,
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
        'timestamp': datetime.now().isoformat()
    }


def run_enhanced_five_step_workflow(
    symbol: str,
    info: Dict,
    position: Dict,
    history: list,
    fund_flow: Dict,
    deepseek_api_key: str,
    qwen_api_key: str,
    prompt_templates: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    运行增强版五步 MoE 深度研判工作流
    
    Args:
        symbol: 股票代码
        info: 实时行情数据
        position: 持仓数据
        history: 交易历史
        fund_flow: 资金流向数据
        deepseek_api_key: DeepSeek API Key
        qwen_api_key: Qwen API Key
        prompt_templates: 提示词模板
        
    Returns:
        Dict 包含所有步骤的结果
    """
    start_time = datetime.now()
    print("=" * 70)
    print("🚀 启动增强版五步 MoE 深度研判工作流")
    print(f"   标的: {symbol} ({info.get('name', 'N/A')})")
    print(f"   当前价: {info.get('price', 0)}")
    print("   特点: 整合技术/基本面/资金/情报四维分析")
    print("=" * 70)
    
    # Step 0: 数据整合
    print("\n📥 Step 0: 整合多维度数据...")
    integrator = DataIntegrator(symbol)
    enriched_data = integrator.load_all_data()
    
    data_summary = enriched_data.get('enriched_data_summary', {})
    print(f"   ✅ 技术面数据: {'✓' if enriched_data.get('technical', {}).get('data_available') else '✗'}")
    print(f"   ✅ 基本面数据: {'✓' if enriched_data.get('fundamental', {}).get('data_available') else '✗'}")
    print(f"   ✅ 资金面数据: {'✓' if enriched_data.get('fund_flow', {}).get('data_available') else '✗'}")
    print(f"   ✅ 情报库数据: {'✓' if enriched_data.get('intelligence', {}).get('data_available') else '✗'}")
    print(f"   ✅ 历史研报: {len(enriched_data.get('research_history', []))}份")
    print(f"   ✅ 历史策略: {len(enriched_data.get('strategy_history', []))}条")
    
    # 加载提示词模板
    if prompt_templates is None:
        prompt_templates = _load_prompt_templates()
    
    results = {}
    workflow_history = []
    
    try:
        # Step 1: 蓝军深度分析
        results['draft'] = step1_blue_draft_enhanced(
            symbol=symbol,
            info=info,
            position=position,
            history=history,
            fund_flow=fund_flow,
            deepseek_api_key=deepseek_api_key,
            enriched_data=enriched_data,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['draft'])
        
        # Step 2: 红军深度审计
        results['audit'] = step2_red_audit_enhanced(
            symbol=symbol,
            info=info,
            blue_draft=results['draft'],
            enriched_data=enriched_data,
            qwen_api_key=qwen_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['audit'])
        
        # Step 3: 蓝军深度优化
        results['refined'] = step3_blue_refinement_enhanced(
            symbol=symbol,
            info=info,
            blue_draft=results['draft'],
            red_audit=results['audit'],
            enriched_data=enriched_data,
            deepseek_api_key=deepseek_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['refined'])
        
        # Step 4: 红军最终裁决
        results['verdict'] = step4_red_verdict_enhanced(
            symbol=symbol,
            info=info,
            blue_refinement=results['refined'],
            enriched_data=enriched_data,
            qwen_api_key=qwen_api_key,
            prompt_templates=prompt_templates
        )
        workflow_history.append(results['verdict'])
        
        # Step 5: 最终执行令
        results['final'] = step5_blue_final_order_enhanced(
            symbol=symbol,
            info=info,
            position=position,
            workflow_history=workflow_history,
            enriched_data=enriched_data,
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
            },
            'data_dimensions': {
                'technical': enriched_data.get('technical', {}).get('data_available', False),
                'fundamental': enriched_data.get('fundamental', {}).get('data_available', False),
                'fund_flow': enriched_data.get('fund_flow', {}).get('data_available', False),
                'intelligence': enriched_data.get('intelligence', {}).get('data_available', False),
                'research_history': len(enriched_data.get('research_history', [])),
                'strategy_history': len(enriched_data.get('strategy_history', []))
            }
        }
        
        # 添加最终执行令的便捷引用
        results['final_order'] = results['final']['final_order']
        
        print("\n" + "=" * 70)
        print(f"✅ 增强版五步 MoE 深度研判完成! 总耗时: {duration:.1f} 秒")
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


# 保持向后兼容
run_five_step_workflow = run_enhanced_five_step_workflow


if __name__ == "__main__":
    print("增强版五步 MoE 深度研判模块加载成功")
    print("用法: from scripts.five_step_moe_enhanced import run_enhanced_five_step_workflow")
