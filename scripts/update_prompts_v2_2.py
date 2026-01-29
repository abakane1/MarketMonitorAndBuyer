import sys
import os

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import load_config, save_config

def update_v2_2_prompts():
    print("Loading config...")
    config = load_config()
    prompts = config.get("prompts", {})
    
    # New Blue Team Final Decision Prompt
    FINAL_DECISION_PROMPT = """
【指令类型】Final Execution Order (v3.0 Final)

【背景】
你提交了策略 v2.0，经过了红军（首席审计师）的【终极裁决】。
现在你需要阅读裁决结果，发布最终执行令。

【红军终审裁决】
{final_verdict}

【你的任务】
1. **确认状态**: 红军是批准(Approved)还是驳回(Rejected)？
2. **发布命令**: 
   - 如果被驳回：宣布**放弃交易**，并简述理由。
   - 如果被批准：请基于 v2.0 策略，输出一份**极度精简**的最终执行单，供交易员直接执行。去除所有废话和分析过程。

【输出格式】
[决策] 执行 / 放弃
[标的] 代码 / 名称
[方向] 买入 / 卖出
[价格] <具体数值>
[数量] <股数>
[止损] <严格止损位>
[止盈] <目标位>
[有效期] 仅限今日

(最后附上一句简短的指挥官寄语)
"""

    print("Injecting 'deepseek_final_decision'...")
    prompts["deepseek_final_decision"] = FINAL_DECISION_PROMPT
    
    config["prompts"] = prompts
    save_config(config)
    print("Done! v2.2.0 Prompts Updated.")

if __name__ == "__main__":
    update_v2_2_prompts()
