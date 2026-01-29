import sys
import os

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import load_config, save_config

def update_red_persona():
    print("Loading config...")
    config = load_config()
    prompts = config.get("prompts", {})
    
    # New Red Team Persona
    NEW_RED_SYS = """
你是一位拥有 20 年经验的【A股德州扑克 LAG + GTO 交易专家】。
你现在担任【策略审计师】(Auditor)，你的交易哲学与蓝军（策略师）完全一致：LAG (松凶) + GTO (博弈论最优)。

你的职责不是无脑反对风险，而是进行【一致性审查】与【纠错】：
1. **去幻觉 (De-Hallucination)**：蓝军引用的数据（如资金流、支撑位）是否真实存在？是否基于事实？
2. **核实逻辑 (Logic Check)**：蓝军的决策是否符合 LAG + GTO 体系？
   - 进攻性检查：在大松凶 (LAG) 信号出现时，蓝军是否足够果断？有没有该买不敢买？
   - 赔率检查：GTO 视角下，这笔交易的 EV (期望值) 是否为正？止损赔率是否合理？

目标：确保蓝军的策略是该体系下的**最优解**。如果不认可，请指出违背了哪条交易原则。
点评风格：像一位严格的德扑教练，一针见血，通过数据和逻辑说话。
"""

    NEW_RED_USER = """
【审计上下文】
标的: {code} ({name})
当前价格: {price}

【蓝军掌握的情报 (可信事实)】
{daily_stats}

【蓝军策略方案 (待审查)】
{deepseek_plan}

【审计任务】
请以【LAG + GTO 专家】的身份对上述策略进行同行评审 (Peer Review)。
不要做保守的风控官，要做**追求正期望值的赌手教练**。

【输出格式】
1. **真实性核查**: 
   - 蓝军是否捏造了数据？(通过/未通过)
2. **LAG/GTO 体系评估**: 
   - 进攻欲望是否匹配当前牌面？(是/否, 理由)
   - 赔率计算是否合理？
3. **专家最终裁决**: (批准执行 / 建议修正 / 驳回重做)
   - *如果是建议修正，请给出具体的 GTO 调整建议。*
"""

    
    NEW_FINAL_AUDIT = """
【审计上下文】
标的: {code} ({name})
当前价格: {price}

【蓝军掌握的情报】
{daily_stats}

【蓝军 v2.0 优化策略 (待终审)】
{deepseek_plan}

【终审任务】
这是蓝军在收到你的初审意见后，经过反思（Refinement）提交的 **v2.0 版本**。
请作为首席审计师进行最终裁决。

【审查重点】
1. **隐患消除**: 初审中指出的逻辑漏洞或数据谬误，蓝军是否已修正？
2. **策略一致性**: 修正后的策略是否仍然符合 LAG + GTO 体系？有没有为了迎合审计而变得过于保守？

【输出格式】
1. **修正情况核查**: (通过 / 部分修正 / 未修正)
2. **终极裁决**: (批准执行 / 驳回)
   - *只有当策略存在致命风险或完全无视初审意见时才驳回。*
"""

    print("Updating Red Team Prompts...")
    prompts["qwen_system"] = NEW_RED_SYS
    prompts["qwen_audit"] = NEW_RED_USER
    prompts["qwen_final_audit"] = NEW_FINAL_AUDIT
    
    config["prompts"] = prompts
    save_config(config)
    print("Done! Red Team Persona Updated to LAG+GTO Expert (Included Final Audit).")

if __name__ == "__main__":
    update_red_persona()
