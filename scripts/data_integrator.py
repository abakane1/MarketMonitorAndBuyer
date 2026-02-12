#!/usr/bin/env python3
"""
Enhanced Five-Step MoE (Mixture of Experts) Workflow - Deep Analysis Edition
深度研判升级版 - 整合技术面、基本面、情报面、资金面四维分析

核心升级:
1. 多维度数据整合 (技术/基本面/情报/资金)
2. 历史策略复盘学习
3. 情报权重动态评估
4. 主力意图深度识别
5. 市场情绪量化分析
"""

import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

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


class DataIntegrator:
    """数据整合器 - 聚合所有可用数据源"""
    
    def __init__(self, symbol: str, base_path: str = '/Users/zuliangzhao/MarketMonitorAndBuyer'):
        self.symbol = symbol
        self.base_path = Path(base_path)
        self.stock_data_path = self.base_path / 'stock_data'
        
    def load_all_data(self) -> Dict[str, Any]:
        """加载所有可用数据"""
        data = {
            'symbol': self.symbol,
            'timestamp': datetime.now().isoformat(),
            'technical': self._load_technical_data(),
            'fundamental': self._load_fundamental_data(),
            'fund_flow': self._load_fund_flow_data(),
            'intelligence': self._load_intelligence_data(),
            'research_history': self._load_research_history(),
            'strategy_history': self._load_strategy_history(),
            'minute_data': self._load_minute_data(),
            'market_sentiment': self._analyze_market_sentiment()
        }
        return data
    
    def _load_technical_data(self) -> Dict:
        """加载技术指标数据"""
        try:
            # 从分钟数据计算技术指标
            minute_file = self.stock_data_path / f'{self.symbol}_minute.parquet'
            if minute_file.exists():
                df = pd.read_parquet(minute_file)
                if len(df) > 0:
                    recent = df.tail(240)  # 最近一个交易日
                    return {
                        'current_price': float(df['收盘'].iloc[-1]) if '收盘' in df.columns else None,
                        'price_change_1d': self._calc_price_change(df, 240),
                        'price_change_5d': self._calc_price_change(df, 240*5),
                        'volatility': float(df['收盘'].pct_change().std() * 100) if '收盘' in df.columns else None,
                        'avg_volume': int(recent['成交量'].mean()) if '成交量' in recent.columns else 0,
                        'volume_trend': self._analyze_volume_trend(df),
                        'support_level': self._calc_support_level(df),
                        'resistance_level': self._calc_resistance_level(df),
                        'data_available': True
                    }
        except Exception as e:
            print(f"⚠️ 技术指标加载失败: {e}")
        return {'data_available': False}
    
    def _load_fundamental_data(self) -> Dict:
        """加载基本面数据"""
        fundamental = {'data_available': False}
        try:
            research_file = self.stock_data_path / f'{self.symbol}_research.json'
            if research_file.exists():
                with open(research_file, 'r', encoding='utf-8') as f:
                    research_list = json.load(f)
                    if research_list:
                        # 提取最新的基本面信息
                        latest = research_list[-1]
                        content = latest.get('result', '')
                        
                        # 解析基本面关键信息
                        fundamental = {
                            'data_available': True,
                            'latest_research_date': latest.get('timestamp', 'N/A'),
                            'research_count': len(research_list),
                            'financial_summary': self._extract_financial_info(content),
                            'key_news': self._extract_key_news(content),
                            'risk_factors': self._extract_risk_factors(content),
                            'catalysts': self._extract_catalysts(content)
                        }
        except Exception as e:
            print(f"⚠️ 基本面数据加载失败: {e}")
        return fundamental
    
    def _load_fund_flow_data(self) -> Dict:
        """加载资金流向数据"""
        try:
            fund_flow_file = self.stock_data_path / 'fund_flow_cache.parquet'
            if fund_flow_file.exists():
                df = pd.read_parquet(fund_flow_file)
                symbol_data = df[df['symbol'] == self.symbol]
                if len(symbol_data) > 0:
                    latest = symbol_data.iloc[-1]
                    return {
                        'data_available': True,
                        'main_force_net': latest.get('主力净流入', 0),
                        'main_force_ratio': latest.get('主力净占比', 0),
                        'super_large_net': latest.get('超大单净流入', 0),
                        'large_net': latest.get('大单净流入', 0),
                        'medium_net': latest.get('中单净流入', 0),
                        'small_net': latest.get('小单净流入', 0),
                        '5day_trend': self._calc_fund_flow_trend(df, self.symbol, 5),
                        '10day_trend': self._calc_fund_flow_trend(df, self.symbol, 10),
                        'main_intent': self._analyze_main_intent(df, self.symbol)
                    }
        except Exception as e:
            print(f"⚠️ 资金流向加载失败: {e}")
        return {'data_available': False}
    
    def _load_intelligence_data(self) -> Dict:
        """加载情报库数据"""
        intel = {'data_available': False, 'items': []}
        try:
            db_path = self.stock_data_path / 'intel_hub.db'
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # 获取活跃情报
                cursor.execute("""
                    SELECT content, source, priority, marked_by_user, created_at 
                    FROM intelligence 
                    WHERE symbol = ? AND is_active = 1
                    ORDER BY marked_by_user DESC, priority DESC, created_at DESC
                    LIMIT 10
                """, (self.symbol,))
                
                rows = cursor.fetchall()
                intel['items'] = [{
                    'content': row[0],
                    'source': row[1],
                    'priority': row[2],
                    'marked': bool(row[3]),
                    'date': row[4]
                } for row in rows]
                
                # 获取新闻缓存
                cursor.execute("""
                    SELECT title, content, source, published_at 
                    FROM news_cache 
                    WHERE symbol = ? 
                    ORDER BY published_at DESC 
                    LIMIT 5
                """, (self.symbol,))
                
                news_rows = cursor.fetchall()
                intel['recent_news'] = [{
                    'title': row[0],
                    'content': row[1],
                    'source': row[2],
                    'date': row[3]
                } for row in news_rows]
                
                intel['data_available'] = len(intel['items']) > 0 or len(intel.get('recent_news', [])) > 0
                conn.close()
        except Exception as e:
            print(f"⚠️ 情报库加载失败: {e}")
        return intel
    
    def _load_research_history(self) -> List[Dict]:
        """加载历史研究报告"""
        try:
            research_file = self.stock_data_path / f'{self.symbol}_research.json'
            if research_file.exists():
                with open(research_file, 'r', encoding='utf-8') as f:
                    return json.load(f)[-5:]  # 最近5份报告
        except Exception as e:
            print(f"⚠️ 历史研报加载失败: {e}")
        return []
    
    def _load_strategy_history(self) -> List[Dict]:
        """加载历史策略记录"""
        try:
            strategy_file = self.stock_data_path / f'{self.symbol}_strategies.json'
            if strategy_file.exists():
                with open(strategy_file, 'r', encoding='utf-8') as f:
                    strategies = json.load(f)
                    # 转换为列表并按时间排序
                    return [{'date': k, **v} for k, v in strategies.items()][-5:]
        except Exception as e:
            print(f"⚠️ 历史策略加载失败: {e}")
        return []
    
    def _load_minute_data(self) -> Dict:
        """加载分钟数据摘要"""
        try:
            minute_file = self.stock_data_path / f'{self.symbol}_minute.parquet'
            if minute_file.exists():
                df = pd.read_parquet(minute_file)
                if len(df) > 0:
                    recent_5d = df.tail(240*5)
                    return {
                        'data_available': True,
                        'total_records': len(df),
                        'recent_5d_high': float(recent_5d['最高'].max()) if '最高' in recent_5d.columns else None,
                        'recent_5d_low': float(recent_5d['最低'].min()) if '最低' in recent_5d.columns else None,
                        'price_distribution': {
                            'q25': float(recent_5d['收盘'].quantile(0.25)) if '收盘' in recent_5d.columns else None,
                            'q75': float(recent_5d['收盘'].quantile(0.75)) if '收盘' in recent_5d.columns else None
                        }
                    }
        except Exception as e:
            print(f"⚠️ 分钟数据加载失败: {e}")
        return {'data_available': False}
    
    def _analyze_market_sentiment(self) -> Dict:
        """分析市场情绪"""
        sentiment = {'data_available': False}
        try:
            # 基于资金流向和价格行为分析情绪
            fund_flow = self._load_fund_flow_data()
            technical = self._load_technical_data()
            
            if fund_flow.get('data_available') and technical.get('data_available'):
                # 计算情绪指标
                main_ratio = fund_flow.get('main_force_ratio', 0)
                price_change = technical.get('price_change_1d', 0)
                
                # 综合判断
                if main_ratio > 10 and price_change > 2:
                    sentiment['overall'] = '强烈乐观'
                elif main_ratio > 5:
                    sentiment['overall'] = '乐观'
                elif main_ratio < -10 and price_change < -2:
                    sentiment['overall'] = '强烈悲观'
                elif main_ratio < -5:
                    sentiment['overall'] = '悲观'
                else:
                    sentiment['overall'] = '中性'
                
                sentiment['main_force_attitude'] = '看多' if main_ratio > 5 else '看空' if main_ratio < -5 else '观望'
                sentiment['retail_attitude'] = '跟风' if fund_flow.get('small_net', 0) > 0 else '恐慌'
                sentiment['data_available'] = True
        except Exception as e:
            print(f"⚠️ 情绪分析失败: {e}")
        return sentiment
    
    # Helper methods
    def _calc_price_change(self, df: pd.DataFrame, periods: int) -> float:
        """计算价格变化百分比"""
        try:
            if '收盘' in df.columns and len(df) >= periods:
                return float((df['收盘'].iloc[-1] / df['收盘'].iloc[-periods] - 1) * 100)
        except:
            pass
        return 0.0
    
    def _analyze_volume_trend(self, df: pd.DataFrame) -> str:
        """分析成交量趋势"""
        try:
            if '成交量' in df.columns and len(df) > 480:
                recent = df['成交量'].tail(240).mean()
                previous = df['成交量'].tail(480).head(240).mean()
                ratio = recent / previous if previous > 0 else 1
                if ratio > 1.5:
                    return '放量'
                elif ratio < 0.7:
                    return '缩量'
                return '持平'
        except:
            pass
        return '未知'
    
    def _calc_support_level(self, df: pd.DataFrame) -> float:
        """计算支撑位"""
        try:
            if '最低' in df.columns:
                return float(df['最低'].tail(120).min())
        except:
            pass
        return 0.0
    
    def _calc_resistance_level(self, df: pd.DataFrame) -> float:
        """计算阻力位"""
        try:
            if '最高' in df.columns:
                return float(df['最高'].tail(120).max())
        except:
            pass
        return 0.0
    
    def _extract_financial_info(self, content: str) -> Dict:
        """从研报中提取财务信息"""
        info = {}
        # 简单的关键词提取
        if '营收' in content or '收入' in content:
            info['has_revenue_data'] = True
        if '净利润' in content or '亏损' in content:
            info['has_profit_data'] = True
        if '毛利率' in content:
            info['has_margin_data'] = True
        return info
    
    def _extract_key_news(self, content: str) -> List[str]:
        """提取关键新闻"""
        news = []
        lines = content.split('\n')
        for line in lines:
            if any(keyword in line for keyword in ['公告', '新闻', '消息', '发布', '计划']):
                if len(line) > 10 and len(line) < 200:
                    news.append(line.strip())
        return news[:5]
    
    def _extract_risk_factors(self, content: str) -> List[str]:
        """提取风险因素"""
        risks = []
        risk_keywords = ['风险', '亏损', '负债', '诉讼', '处罚', '退市', '违约', '担保']
        lines = content.split('\n')
        for line in lines:
            if any(kw in line for kw in risk_keywords):
                if len(line) > 10 and len(line) < 200:
                    risks.append(line.strip())
        return risks[:5]
    
    def _extract_catalysts(self, content: str) -> List[str]:
        """提取催化剂"""
        catalysts = []
        catalyst_keywords = ['并购', '重组', '增持', '回购', '股权激励', '新产品', '订单', '合作']
        lines = content.split('\n')
        for line in lines:
            if any(kw in line for kw in catalyst_keywords):
                if len(line) > 10 and len(line) < 200:
                    catalysts.append(line.strip())
        return catalysts[:5]
    
    def _calc_fund_flow_trend(self, df: pd.DataFrame, symbol: str, days: int) -> Dict:
        """计算资金流向趋势"""
        try:
            symbol_data = df[df['symbol'] == symbol].tail(days)
            if len(symbol_data) > 0:
                return {
                    'total_net': float(symbol_data['主力净流入'].sum()),
                    'positive_days': int((symbol_data['主力净流入'] > 0).sum()),
                    'avg_daily': float(symbol_data['主力净流入'].mean())
                }
        except:
            pass
        return {'total_net': 0, 'positive_days': 0, 'avg_daily': 0}
    
    def _analyze_main_intent(self, df: pd.DataFrame, symbol: str) -> str:
        """分析主力意图"""
        try:
            symbol_data = df[df['symbol'] == symbol].tail(10)
            if len(symbol_data) < 5:
                return '数据不足'
            
            recent_net = symbol_data['主力净流入'].tail(3).sum()
            price_trend = symbol_data['close'].iloc[-1] / symbol_data['close'].iloc[0] - 1 if 'close' in symbol_data.columns else 0
            
            if recent_net > 5000 and price_trend > 0.05:
                return '积极建仓'
            elif recent_net > 5000 and price_trend < 0:
                return '逆势吸筹'
            elif recent_net < -5000 and price_trend > 0:
                return '拉高出货'
            elif recent_net < -5000 and price_trend < 0:
                return '恐慌抛售'
            else:
                return '震荡整理'
        except:
            pass
        return '未知'


def format_enriched_context(data: Dict[str, Any]) -> str:
    """将整合的数据格式化为AI可读的文本"""
    lines = []
    lines.append("=" * 60)
    lines.append("【🔍 深度多维数据整合报告】")
    lines.append("=" * 60)
    
    # 1. 技术面分析
    tech = data.get('technical', {})
    if tech.get('data_available'):
        lines.append("\n📊 【技术面分析】")
        lines.append(f"   当前价格: {tech.get('current_price', 'N/A')}")
        lines.append(f"   1日涨跌: {tech.get('price_change_1d', 0):+.2f}%")
        lines.append(f"   5日涨跌: {tech.get('price_change_5d', 0):+.2f}%")
        lines.append(f"   波动率: {tech.get('volatility', 0):.2f}%")
        lines.append(f"   成交量趋势: {tech.get('volume_trend', 'N/A')}")
        lines.append(f"   支撑位: {tech.get('support_level', 'N/A')}")
        lines.append(f"   阻力位: {tech.get('resistance_level', 'N/A')}")
    
    # 2. 资金面分析
    fund = data.get('fund_flow', {})
    if fund.get('data_available'):
        lines.append("\n💰 【资金面分析】")
        lines.append(f"   主力净流入: {fund.get('main_force_net', 0):.0f}万")
        lines.append(f"   主力净占比: {fund.get('main_force_ratio', 0):.2f}%")
        lines.append(f"   超大单流向: {fund.get('super_large_net', 0):.0f}万")
        lines.append(f"   5日资金流向: {fund.get('5day_trend', {}).get('total_net', 0):.0f}万")
        lines.append(f"   主力意图判断: {fund.get('main_intent', '未知')}")
    
    # 3. 基本面分析
    fundamental = data.get('fundamental', {})
    if fundamental.get('data_available'):
        lines.append("\n📈 【基本面分析】")
        lines.append(f"   研报数量: {fundamental.get('research_count', 0)}份")
        lines.append(f"   最新研报日期: {fundamental.get('latest_research_date', 'N/A')}")
        
        risks = fundamental.get('risk_factors', [])
        if risks:
            lines.append(f"   ⚠️ 主要风险因素 ({len(risks)}项):")
            for risk in risks[:3]:
                lines.append(f"      • {risk[:80]}...")
        
        catalysts = fundamental.get('catalysts', [])
        if catalysts:
            lines.append(f"   🚀 潜在催化剂 ({len(catalysts)}项):")
            for cat in catalysts[:3]:
                lines.append(f"      • {cat[:80]}...")
    
    # 4. 市场情绪
    sentiment = data.get('market_sentiment', {})
    if sentiment.get('data_available'):
        lines.append("\n🎭 【市场情绪分析】")
        lines.append(f"   整体情绪: {sentiment.get('overall', 'N/A')}")
        lines.append(f"   主力态度: {sentiment.get('main_force_attitude', 'N/A')}")
        lines.append(f"   散户情绪: {sentiment.get('retail_attitude', 'N/A')}")
    
    # 5. 情报库
    intel = data.get('intelligence', {})
    if intel.get('data_available'):
        lines.append(f"\n📚 【情报库】 ({len(intel.get('items', []))}条核心情报)")
        for item in intel.get('items', [])[:3]:
            prefix = "⭐" if item.get('marked') else "•"
            lines.append(f"   {prefix} [{item.get('priority', 'normal')}] {item.get('content', '')[:100]}...")
    
    # 6. 历史策略复盘
    strategy_history = data.get('strategy_history', [])
    if strategy_history:
        lines.append(f"\n📜 【历史策略复盘】 (最近{len(strategy_history)}次)")
        for i, strat in enumerate(strategy_history[-3:], 1):
            date = strat.get('date', 'N/A')
            advice = strat.get('advice', '')
            # 提取决策方向
            direction = '未知'
            if '卖出' in advice[:500]:
                direction = '卖出'
            elif '买入' in advice[:500]:
                direction = '买入'
            elif '观望' in advice[:500]:
                direction = '观望'
            lines.append(f"   {i}. {date}: {direction}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


# Export for use in five_step_moe
__all__ = ['DataIntegrator', 'format_enriched_context']


if __name__ == "__main__":
    # Test
    integrator = DataIntegrator('600076')
    data = integrator.load_all_data()
    print(format_enriched_context(data))
