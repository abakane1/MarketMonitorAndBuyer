import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import load_config, save_config

def update_refinement():
    print("Loading config...")
    config = load_config()
    prompts = config.get("prompts", {})
    
    NEW_REFINE = """
【来自红军 (审计师) 的反馈】
{audit_report}

【你的任务 / v2.0 迭代】
你是策略专家（蓝军），不是红军的下属。请仔细阅读上述审计意见，并进行**独立判断**：
1. **去伪存真**：如果红军指出的事实错误（如看错数据）确实存在，请修正；如果红军产生了幻觉（错误引用），请在思考中反驳并坚持原判。
2. **吸收建议**：如果红军的 GTO 建议合理（如调整仓位赔率），请优化你的策略。

请输出《交易策略 v2.0 (Refined)》。
- 如果你完全接受红军意见，请修改策略。
- 如果你认为红军错了，请保留原策略并说明理由。
"""
    prompts["refinement_instruction"] = NEW_REFINE
    config["prompts"] = prompts
    save_config(config)
    print("Done! Refinement Instruction Updated.")

if __name__ == "__main__":
    update_refinement()
