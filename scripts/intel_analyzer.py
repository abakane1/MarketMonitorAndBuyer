#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情报智能分析模块 (Intelligence Analyzer)

v4.1.0 Week 2 - Intelligence Hub 2.0 Phase 2
功能:
1. 调用DeepSeek API分析情报内容
2. 自动关联ETF代码和置信度
3. 判断利好/利空情感
4. 保存到数据库

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.ai_advisor import call_ai_model

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = Path("stock_data/intel_hub.db")


@dataclass
class IntelAnalysisResult:
    """情报分析结果"""
    symbol: str              # ETF代码
    confidence: float        # 置信度 0-1
    sentiment: str           # bullish/bearish/neutral
    reasoning: str           # 推理过程
    keywords: List[str]      # 提取的关键词


class IntelligenceAnalyzer:
    """
    情报智能分析器
    
    使用DeepSeek Reasoner分析情报内容，自动关联ETF
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
        self.etf_configs = self._load_etf_configs()
    
    def _load_api_key(self) -> Optional[str]:
        """从配置文件加载API Key"""
        try:
            config_path = Path("user_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # 根据实际配置结构调整
                    settings = config.get('settings', {})
                    # 优先使用deepseek，其次是kimi
                    return settings.get('deepseek_api_key') or settings.get('kimi_api_key')
        except Exception as e:
            logger.warning(f"加载API Key失败: {e}")
        return None
    
    def _load_etf_configs(self) -> Dict[str, Dict]:
        """加载ETF配置"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, name, keywords, tags FROM etf_keywords")
            configs = {}
            for row in cursor.fetchall():
                symbol, name, keywords_json, tags_json = row
                configs[symbol] = {
                    'name': name,
                    'keywords': json.loads(keywords_json) if keywords_json else [],
                    'tags': json.loads(tags_json) if tags_json else []
                }
            conn.close()
            return configs
        except Exception as e:
            logger.error(f"加载ETF配置失败: {e}")
            # 返回默认配置
            return {
                '588200': {'name': '科创芯片ETF', 'keywords': ['芯片', '半导体', '中芯国际']},
                '588710': {'name': '科创半导体设备ETF', 'keywords': ['半导体设备', '光刻机']},
                '588750': {'name': '科创芯片ETF(汇添富)', 'keywords': ['芯片', '半导体']}
            }
    
    def _build_analysis_prompt(self, content: str) -> str:
        """构建分析提示词"""
        etf_list = []
        for symbol, config in self.etf_configs.items():
            keywords = ', '.join(config['keywords'][:5])
            etf_list.append(f"- {symbol}: {config['name']}, 关键词: {keywords}")
        
        etf_section = '\n'.join(etf_list)
        
        prompt = f"""你是一个金融情报分析助手。请分析以下情报，判断它与哪些ETF相关。

用户关注的ETF列表:
{etf_section}

情报内容:
{content}

请分析并输出JSON格式:
{{
    "analyses": [
        {{
            "symbol": "ETF代码",
            "confidence": 0.95,
            "sentiment": "bullish|bearish|neutral",
            "reasoning": "分析理由",
            "keywords": ["关键词1", "关键词2"]
        }}
    ]
}}

要求:
1. confidence: 0-1之间，表示关联置信度
2. sentiment: bullish(利好)/bearish(利空)/neutral(中性)
3. 只返回JSON，不要其他内容
"""
        return prompt
    
    def analyze_content(self, content: str) -> List[IntelAnalysisResult]:
        """
        分析情报内容
        
        Args:
            content: 情报内容
            
        Returns:
            分析结果列表
        """
        prompt = self._build_analysis_prompt(content)
        
        try:
            # 调用DeepSeek Reasoner
            content, reasoning = call_ai_model(
                model_name="deepseek",
                specific_model="deepseek-reasoner",
                user_prompt=prompt,
                api_key=self.api_key,
                system_prompt="你是一个专业的金融情报分析师。"
            )
            
            # 解析JSON响应
            result = self._parse_analysis_response(content)
            return result
            
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return []
    
    def _parse_analysis_response(self, response: str) -> List[IntelAnalysisResult]:
        """解析AI响应"""
        results = []
        
        try:
            # 提取JSON部分
            json_str = response
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                json_str = response.split('```')[1].split('```')[0]
            
            data = json.loads(json_str.strip())
            
            for item in data.get('analyses', []):
                # 过滤低置信度
                confidence = item.get('confidence', 0)
                if confidence >= 0.5:  # 默认阈值50%
                    results.append(IntelAnalysisResult(
                        symbol=item.get('symbol', ''),
                        confidence=confidence,
                        sentiment=item.get('sentiment', 'neutral'),
                        reasoning=item.get('reasoning', ''),
                        keywords=item.get('keywords', [])
                    ))
            
            # 按置信度排序
            results.sort(key=lambda x: x.confidence, reverse=True)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 响应: {response[:200]}")
        except Exception as e:
            logger.error(f"解析失败: {e}")
        
        return results
    
    def save_analysis(self, intel_id: int, analyses: List[IntelAnalysisResult]) -> bool:
        """
        保存分析结果到数据库
        
        Args:
            intel_id: 情报ID
            analyses: 分析结果列表
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 获取情报内容用于更新
            cursor.execute("SELECT content FROM intelligence WHERE id = ?", (intel_id,))
            row = cursor.fetchone()
            if not row:
                logger.error(f"情报ID {intel_id} 不存在")
                return False
            
            # 更新情报表的confidence和sentiment (取最高置信度的)
            if analyses:
                top = analyses[0]
                cursor.execute(
                    "UPDATE intelligence SET confidence = ?, sentiment = ? WHERE id = ?",
                    (top.confidence, top.sentiment, intel_id)
                )
            
            # 插入关联表
            for analysis in analyses:
                cursor.execute(
                    """INSERT OR REPLACE INTO intelligence_stocks 
                       (intelligence_id, symbol, confidence) VALUES (?, ?, ?)""",
                    (intel_id, analysis.symbol, analysis.confidence)
                )
            
            conn.commit()
            conn.close()
            
            logger.info(f"情报 {intel_id} 分析结果已保存，关联 {len(analyses)} 个ETF")
            return True
            
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
            return False
    
    def analyze_and_save(self, intel_id: int, content: str) -> List[IntelAnalysisResult]:
        """
        分析情报并保存结果
        
        Args:
            intel_id: 情报ID
            content: 情报内容
            
        Returns:
            分析结果列表
        """
        logger.info(f"开始分析情报 {intel_id}...")
        
        analyses = self.analyze_content(content)
        
        if analyses:
            self.save_analysis(intel_id, analyses)
            logger.info(f"情报 {intel_id} 分析完成，关联ETF: {[a.symbol for a in analyses]}")
        else:
            logger.warning(f"情报 {intel_id} 分析未返回结果")
        
        return analyses


def analyze_pending_intelligence(limit: int = 10):
    """
    分析待处理的情报
    
    Usage:
        python scripts/intel_analyzer.py --pending
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 查询没有关联记录的情报
        cursor.execute("""
            SELECT i.id, i.content 
            FROM intelligence i
            LEFT JOIN intelligence_stocks s ON i.id = s.intelligence_id
            WHERE s.intelligence_id IS NULL AND i.is_active = 1
            LIMIT ?
        """, (limit,))
        
        pending = cursor.fetchall()
        conn.close()
        
        if not pending:
            print("✅ 没有待分析的情报")
            return
        
        print(f"📝 发现 {len(pending)} 条待分析情报")
        
        analyzer = IntelligenceAnalyzer()
        
        for intel_id, content in pending:
            print(f"\n🔄 分析情报 {intel_id}...")
            results = analyzer.analyze_and_save(intel_id, content)
            
            if results:
                print(f"   ✅ 关联ETF:")
                for r in results:
                    emoji = "🟢" if r.sentiment == "bullish" else "🔴" if r.sentiment == "bearish" else "⚪"
                    print(f"      {emoji} {r.symbol}: 置信度{r.confidence:.0%}, 情感{r.sentiment}")
            else:
                print(f"   ⚠️ 未识别到相关ETF")
        
        print(f"\n✅ 完成 {len(pending)} 条情报分析")
        
    except Exception as e:
        logger.error(f"批量分析失败: {e}")


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="情报智能分析工具")
    parser.add_argument("--pending", action="store_true", help="分析待处理的情报")
    parser.add_argument("--test", action="store_true", help="测试分析功能")
    parser.add_argument("--content", type=str, help="分析指定内容")
    parser.add_argument("--limit", type=int, default=10, help="限制数量")
    
    args = parser.parse_args()
    
    if args.test:
        # 测试模式
        test_content = "中芯国际发布最新财报，业绩超预期增长，芯片板块迎来重大利好。"
        print(f"🧪 测试分析: {test_content}")
        
        analyzer = IntelligenceAnalyzer()
        results = analyzer.analyze_content(test_content)
        
        print(f"\n分析结果:")
        for r in results:
            print(f"  • {r.symbol}: 置信度{r.confidence:.0%}, 情感{r.sentiment}")
            print(f"    理由: {r.reasoning[:100]}...")
    
    elif args.content:
        # 分析指定内容
        analyzer = IntelligenceAnalyzer()
        results = analyzer.analyze_content(args.content)
        
        print(f"分析结果:")
        for r in results:
            emoji = "🟢" if r.sentiment == "bullish" else "🔴" if r.sentiment == "bearish" else "⚪"
            print(f"{emoji} {r.symbol}: 置信度{r.confidence:.0%}")
            print(f"   情感: {r.sentiment}")
            print(f"   理由: {r.reasoning}")
            print(f"   关键词: {', '.join(r.keywords)}")
    
    elif args.pending:
        # 分析待处理情报
        analyze_pending_intelligence(limit=args.limit)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    main()
