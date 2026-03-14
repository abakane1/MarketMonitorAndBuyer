# -*- coding: utf-8 -*-
"""
ETF专属情报时间轴组件 (Intelligence Timeline)

v4.1.0 Week 3 - Intelligence Hub 2.0 Phase 4
功能:
1. ETF专属情报展示页面
2. 情报时间轴可视化
3. 持仓股票情报联动
4. 情感标签可视化

Author: AI Programmer
Date: 2026-03-14
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_fetcher import get_stock_realtime_info

DB_PATH = Path("stock_data/intel_hub.db")


class ETFIntelligenceView:
    """ETF情报视图"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.etf_info = self._load_etf_info()
    
    def _load_etf_info(self) -> Dict:
        """加载ETF信息"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, keywords, tags FROM etf_keywords WHERE symbol = ?",
                (self.symbol,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'name': row[0],
                    'keywords': json.loads(row[1]) if row[1] else [],
                    'tags': json.loads(row[2]) if row[2] else []
                }
        except Exception as e:
            st.error(f"加载ETF信息失败: {e}")
        
        return {'name': self.symbol, 'keywords': [], 'tags': []}
    
    def get_intelligence(self, days: int = 30, include_archived: bool = False) -> List[Dict]:
        """
        获取ETF相关情报
        
        Args:
            days: 查询天数
            include_archived: 是否包含已归档情报
            
        Returns:
            情报列表
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 联合查询：直接关联的 + 通过symbol字段的
            query = """
                SELECT DISTINCT i.id, i.content, i.source, i.priority, 
                       i.sentiment, i.confidence, i.created_at, i.summary
                FROM intelligence i
                LEFT JOIN intelligence_stocks s ON i.id = s.intelligence_id
                WHERE (s.symbol = ? OR i.symbol = ?)
                AND i.created_at > datetime('now', '-{} days')
                AND i.is_active = 1
                {}
                ORDER BY i.created_at DESC
            """.format(days, "AND i.is_archived = 0" if not include_archived else "")
            
            cursor.execute(query, (self.symbol, self.symbol))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'content': row[1],
                    'source': row[2],
                    'priority': row[3],
                    'sentiment': row[4] or 'neutral',
                    'confidence': row[5] or 0.5,
                    'created_at': row[6],
                    'summary': row[7],
                    'is_archived': row[7] is not None
                })
            
            conn.close()
            return results
            
        except Exception as e:
            st.error(f"查询情报失败: {e}")
            return []
    
    def render_header(self):
        """渲染页面头部"""
        # 获取实时行情
        try:
            quote = get_stock_realtime_info(self.symbol)
            if quote:
                price = quote.get('price', 0)
                pre_close = quote.get('pre_close', price)
                change_pct = (price - pre_close) / pre_close * 100 if pre_close else 0
                
                # 显示标题和行情
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.title(f"{self.symbol} {self.etf_info['name']}")
                    # 标签
                    tags = self.etf_info.get('tags', [])
                    if tags:
                        st.caption(" ".join([f"`{t}`" for t in tags]))
                
                with col2:
                    color = "🟢" if change_pct >= 0 else "🔴"
                    st.metric(
                        label="最新价",
                        value=f"{price:.3f}",
                        delta=f"{change_pct:+.2f}%"
                    )
            else:
                st.title(f"{self.symbol} {self.etf_info['name']}")
        except Exception:
            st.title(f"{self.symbol} {self.etf_info['name']}")
        
        st.divider()
    
    def render_timeline(self, intelligence_list: List[Dict]):
        """渲染情报时间轴"""
        if not intelligence_list:
            st.info("📭 暂无相关情报")
            return
        
        st.subheader(f"📊 情报时间轴 ({len(intelligence_list)} 条)")
        
        # 按日期分组
        grouped = {}
        for intel in intelligence_list:
            date = intel['created_at'][:10]  # YYYY-MM-DD
            if date not in grouped:
                grouped[date] = []
            grouped[date].append(intel)
        
        # 渲染时间轴
        for date in sorted(grouped.keys(), reverse=True):
            st.markdown(f"### 📅 {date}")
            
            for intel in grouped[date]:
                self._render_intel_card(intel)
            
            st.divider()
    
    def _render_intel_card(self, intel: Dict):
        """渲染单条情报卡片"""
        # 情感标签
        sentiment = intel.get('sentiment', 'neutral')
        sentiment_config = {
            'bullish': {'emoji': '🟢', 'color': 'green', 'label': '利好'},
            'bearish': {'emoji': '🔴', 'color': 'red', 'label': '利空'},
            'neutral': {'emoji': '⚪', 'color': 'gray', 'label': '中性'}
        }
        config = sentiment_config.get(sentiment, sentiment_config['neutral'])
        
        # 优先级样式
        priority = intel.get('priority', 'normal')
        priority_style = {
            'high': '**🔥 高优先级**',
            'normal': '',
            'low': ''
        }.get(priority, '')
        
        # 卡片内容
        with st.container():
            cols = st.columns([0.1, 0.9])
            
            with cols[0]:
                st.markdown(f"### {config['emoji']}")
            
            with cols[1]:
                # 头部信息
                header_cols = st.columns([2, 1, 1])
                with header_cols[0]:
                    if priority_style:
                        st.markdown(priority_style)
                with header_cols[1]:
                    confidence = intel.get('confidence', 0.5)
                    st.caption(f"置信度: {confidence:.0%}")
                with header_cols[2]:
                    st.caption(f"来源: {intel.get('source', '未知')}")
                
                # 内容
                content = intel.get('content', '')
                if intel.get('is_archived') and intel.get('summary'):
                    content = intel['summary']
                    st.caption("📦 已归档")
                
                st.write(content[:200] + "..." if len(content) > 200 else content)
                
                # 展开查看详情
                with st.expander("查看详情"):
                    st.write(content)
                    st.caption(f"创建时间: {intel['created_at']}")
                    if intel.get('is_archived'):
                        st.info("此情报已归档，仅显示摘要")
    
    def render_filters(self) -> Dict:
        """渲染筛选器"""
        st.sidebar.header("🔍 筛选器")
        
        # 时间范围
        days = st.sidebar.slider("时间范围", 7, 365, 30, key=f"days_{self.symbol}")
        
        # 情感筛选
        sentiment_options = st.sidebar.multiselect(
            "情感标签",
            options=['bullish', 'bearish', 'neutral'],
            default=['bullish', 'bearish', 'neutral'],
            format_func=lambda x: {'bullish': '🟢 利好', 'bearish': '🔴 利空', 'neutral': '⚪ 中性'}[x],
            key=f"sentiment_{self.symbol}"
        )
        
        # 是否包含归档
        include_archived = st.sidebar.checkbox("包含已归档情报", value=False, key=f"archived_{self.symbol}")
        
        return {
            'days': days,
            'sentiments': sentiment_options,
            'include_archived': include_archived
        }
    
    def render(self):
        """渲染完整页面"""
        # 头部
        self.render_header()
        
        # 筛选器
        filters = self.render_filters()
        
        # 获取情报
        intelligence = self.get_intelligence(
            days=filters['days'],
            include_archived=filters['include_archived']
        )
        
        # 按情感筛选
        if filters['sentiments']:
            intelligence = [i for i in intelligence if i['sentiment'] in filters['sentiments']]
        
        # 统计
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 统计")
        st.sidebar.write(f"情报总数: {len(intelligence)}")
        
        sentiment_counts = {}
        for i in intelligence:
            s = i['sentiment']
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        
        for sentiment, count in sentiment_counts.items():
            emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '⚪'}.get(sentiment, '⚪')
            label = {'bullish': '利好', 'bearish': '利空', 'neutral': '中性'}.get(sentiment, sentiment)
            st.sidebar.write(f"{emoji} {label}: {count} 条")
        
        # 时间轴
        self.render_timeline(intelligence)


def render_intel_hub_page():
    """渲染情报中心页面 (供Streamlit调用)"""
    st.set_page_config(
        page_title="ETF情报中心",
        page_icon="📊",
        layout="wide"
    )
    
    st.sidebar.title("📊 ETF情报中心")
    
    # ETF选择
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, name FROM etf_keywords ORDER BY symbol")
        etfs = cursor.fetchall()
        conn.close()
        
        etf_options = {f"{s} - {n}": s for s, n in etfs}
        selected = st.sidebar.selectbox("选择ETF", list(etf_options.keys()))
        selected_symbol = etf_options[selected]
    except Exception:
        selected_symbol = st.sidebar.text_input("输入ETF代码", value="588200")
    
    # 刷新按钮
    if st.sidebar.button("🔄 刷新数据"):
        st.rerun()
    
    # 渲染页面
    view = ETFIntelligenceView(selected_symbol)
    view.render()


if __name__ == "__main__":
    # 独立运行测试
    render_intel_hub_page()
