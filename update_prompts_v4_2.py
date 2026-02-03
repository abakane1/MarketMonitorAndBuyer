import json
import os
from utils.security import decrypt_dict, encrypt_dict, is_encrypted

PROMPTS_FILE = "prompts_encrypted.json"

def update():
    if not os.path.exists(PROMPTS_FILE): return

    with open(PROMPTS_FILE, "r", encoding='utf-8') as f:
        data = json.load(f)
        encrypted_token = data.get("prompts")
        
    if not encrypted_token or not is_encrypted(encrypted_token): return
        
    prompts = decrypt_dict(encrypted_token)
    
    # Update Proposer System to emphasize SCENARIOS
    prompts["proposer_system"] = prompts["proposer_system"] + """
【场景演变指令 (Scenario-based Tactics)】:
1. **拒绝机械化**：严禁仅给出一个固定数值。你的核心任务是描绘【开盘场景】与【盘中演变】。
2. **场景对策**：必须在输出中包含 `【场景对策】` 模块。
   - 场景 A (高开/强势): 触发条件 -> 对应动作。
   - 场景 B (低开/弱势): 触发条件 -> 对应动作。
   - 场景 C (意外杀跌/放量): ...
3. **决策摘要更新**：在决策摘要中，增加一行 `场景重点: [关键转折信号]`。
"""

    # Update Pre-Market Template Format
    prompts["proposer_premarket_suffix"] = """
# 数字化身：场景化博弈规划 (v4.2)

## Context
{daily_stats}
{capital_flow}
{research_context}

## Digital Twin Task
1. **拒绝盲目预测**：不要押注某一种走势。作为博弈专家，你要演练 2-3 种可能的【开盘演变】。
2. **制定应对手册**：针对不同开盘幅度、成交量水平给出差异化操作。

## Output Format
【实战风格镜像】: ...
【场景对策】:
- **场景 A (若强势...)**: ...
- **场景 B (若低迷...)**: ...
【执行令 (v4.0)】:
方向: [观望/买入/卖出/持有]
建议价格: [关键位或区间]
建议股数: [动作描绘而非机械数值]
止损参考: [逻辑位]
止盈参考: [逻辑位]
场景重点: [一句话提醒今日命门]
"""
    
    # Save Back
    new_encrypted = encrypt_dict(prompts)
    data["prompts"] = new_encrypted
    data["version"] = "4.2.0 (Scenario Based)"
    
    with open(PROMPTS_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Prompts updated successfully to v4.2.0 (Scenario Based).")

if __name__ == "__main__":
    update()
