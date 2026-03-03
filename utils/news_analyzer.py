# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime
from utils.ai_advisor import call_deepseek_api, call_qwen_api, call_kimi_api, call_ai_model
from utils.database import get_db_connection
from utils.config import load_config
from utils.data_fetcher import get_stock_news_raw
from utils.intel_manager import update_stock_intel

logger = logging.getLogger(__name__)

class NewsAnalyzer:
    """新闻情绪分析提取器，用于判断新闻利好/利空，并提取对标的的影响。"""
    
    SYSTEM_PROMPT = """你是一位资深的A股证券分析师，专注于量化基本面和新闻舆情分析。
你的任务是阅读输入的新闻或公告，分析其对特定股票的影响，并提取出结构化的情绪数据。

你需要返回如下JSON格式的内容（必须是合法的JSON格式，不包含Markdown外壳）：
{
    "sentiment": "情绪分类", // 只能是 "利好", "利空", "中性" 之一
    "impact_level": "影响程度", // 只能是 "无影响", "轻微", "中等", "重大" 之一
    "summary": "一句话新闻核心摘要", // 20字以内
    "analysis": "核心逻辑分析" // 50字以内，简述为什么是这个情绪，对股价会有什么影响点
}"""

    @classmethod
    def analyze_news(cls, symbol: str, stock_name: str, news_content: str, api_keys: dict, model: str = "DeepSeek") -> dict:
        """
        调用 LLM 分析新闻情绪
        """
        user_prompt = f"""
分析以下涉及【{stock_name} ({symbol})】的新闻/公告：

【新闻内容】
{news_content}

请严格按照指定的 JSON 结构返回你的分析结果。分析应当客观、专业，结合当前A股市场环境。
"""
        
        # Determine which key to use based on the model
        if model.lower() == "deepseek":
            api_key = api_keys.get("deepseek_api_key")
        elif model.lower() == "kimi":
            api_key = api_keys.get("kimi_api_key")
        elif model.lower() == "qwen":
            api_key = api_keys.get("qwen_api_key") or api_keys.get("dashscope_api_key")
        else:
            api_key = api_keys.get("deepseek_api_key")
            
        if not api_key:
             logger.error(f"Missing API key for {model}")
             return {
                 "sentiment": "中性",
                 "impact_level": "未知",
                 "summary": "分析失败：缺少 API Key",
                 "analysis": ""
             }

        try:
             res_content, _ = call_ai_model(model.lower(), api_key, cls.SYSTEM_PROMPT, user_prompt)
             
             # 提取 JSON
             import re
             json_match = re.search(r'(\{.*\})', res_content, re.DOTALL)
             if json_match:
                 res_json = json.loads(json_match.group(1))
                 return res_json
             else:
                 res_json = json.loads(res_content)
                 return res_json
                 
        except Exception as e:
            logger.error(f"News analysis failed for {symbol}: {e}")
            return {
                 "sentiment": "中性",
                 "impact_level": "未知",
                 "summary": "分析失败：模型异常",
                 "analysis": str(e)
             }
             
    @classmethod
    def process_and_store_news(cls, symbol: str, stock_name: str, api_keys: dict, model: str = "DeepSeek"):
        """
        获取、分析并存储新闻
        """
        logger.info(f"开始处理 {stock_name} ({symbol}) 的新闻...")
        
        # 1. 获取最新新闻 (最多取前3条重要的即可，避免API超载)
        # 注意: get_stock_news_raw in v3.2.0 reads cached files downloaded by the scheduler
        news_list = get_stock_news_raw(symbol, n=3)
        if not news_list:
            logger.info(f"未找到 {symbol} 的近期新闻。")
            return []
            
        analyzed_results = []
        for news_item in news_list:
            # 简单清洗
            content = f"标题：{news_item.get('title', '')}\n来源：{news_item.get('source', '')}\n时间：{news_item.get('date', '')}\n内容摘要：{news_item.get('content', '')}"
            
            # 去重：检查是否已经分析过（可以存入数据库或对比摘要，为简单起见这里直接调用）
            # 实践中应当根据 url 或 md5 去重
            res = cls.analyze_news(symbol, stock_name, content, api_keys, model)
            res['date'] = news_item.get('date', '')
            res['title'] = news_item.get('title', '')
            analyzed_results.append(res)
            
        # 2. 将重大或中等影响的新闻汇入情报库
        for item in analyzed_results:
            if item.get('impact_level') in ['重大', '中等'] and item.get('sentiment') != '中性':
                intel_desc = f"({item['date']}) [{item['sentiment']}] {item['summary']} - {item['analysis']}"
                
                logger.info(f"添加新闻情报: {intel_desc}")
                # We use intel_manager to update the intelligence pool
                # update_stock_intel supports accumulating intelligence
                try:
                    update_stock_intel(symbol, intel_desc)
                except Exception as e:
                    logger.error(f"Failed to update intelligence pool: {e}")
                    
        return analyzed_results

def run_news_analysis_batch():
    """批量对所有持有和关注的股票进行新闻分析"""
    config = load_config()
    settings = config.get("settings", {})
    api_keys = {
        "deepseek_api_key": settings.get("deepseek_api_key"),
        "qwen_api_key": settings.get("qwen_api_key") or settings.get("dashscope_api_key"),
        "kimi_api_key": settings.get("kimi_api_key"),
        "kimi_base_url": settings.get("kimi_base_url")
    }
    
    # 优先使用处理更快的模型如 Kimi
    preferred_model = "Kimi" if api_keys.get("kimi_api_key") else "DeepSeek"
    
    target_stocks = {}
    for item in config.get("watchlist", []):
        target_stocks[item['code']] = item.get('name', '未知')
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT symbol, name FROM positions WHERE shares > 0")
        for row in cur.fetchall():
            target_stocks[row['symbol']] = row['name'] if row['name'] else '未知'
        conn.close()
    except Exception as e:
        logger.warning(f"无法读取持仓记录: {e}")

    for code, name in target_stocks.items():
         NewsAnalyzer.process_and_store_news(code, name, api_keys, model=preferred_model)
         
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    run_news_analysis_batch()
