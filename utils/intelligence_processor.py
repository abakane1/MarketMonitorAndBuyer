
import requests
import json
from utils.config import get_settings

def summarize_intelligence(api_key, news_items, stock_symbol, prompt_templates=None):
    """
    Summarizes a list of news items into a concise market sentiment briefing.
    """
    if not news_items:
        return ""
    
    # 从提示词中心加载系统提示词 (v3.2.0)
    if prompt_templates is None:
        try:
            from utils.prompt_loader import load_all_prompts
            prompt_templates = load_all_prompts()
        except Exception:
            prompt_templates = {}
        
    # Format raw text
    raw_text = ""
    for idx, news in enumerate(news_items[:20]): # Limit to top 20
        title = news.get("title", "")
        content = news.get("content", news.get("snippet", ""))
        date = news.get("date", "")
        raw_text += f"[{idx+1}] {date} {title}\n{content[:200]}\n\n"
    
    # v3.2.0: 从提示词中心加载，避免硬编码
    system_prompt = prompt_templates.get("intelligence_processor_system") or (
        "你是一位金融情报分析师。你的任务是从杂乱的新闻流中提取与该股票最相关、最具市场影响力的核心信息。\n"
        "过滤掉无意义的噪音（如自动生成的涨跌播报），重点关注：\n"
        "1. 行业政策利好/利空\n"
        "2. 公司重组、业绩预告、大额订单\n"
        "3. 市场情绪拐点信号\n"
        "输出格式要求：简洁的Markdown列表，分为【重大利好】、【重大利空】、【中性/不确定】三类。如果无相关信息，则留空。"
    )
    
    user_prompt = f"目标标的: {stock_symbol}\n\n情报源:\n{raw_text}"
    
    # Reuse call_deepseek_api logic but maybe simplified or separate
    # For now, simplistic inline implementation or import
    from utils.ai_advisor import call_deepseek_api
    
    content, reasoning = call_deepseek_api(api_key, system_prompt, user_prompt)
    
    return content

