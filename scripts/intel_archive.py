#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情报自动归档模块 (Intelligence Archive)

v4.1.0 Week 2 - Intelligence Hub 2.0 Phase 3
功能:
1. 自动归档6个月前的情报
2. 使用LLM压缩摘要
3. 清理过期数据

Author: AI Programmer
Date: 2026-03-14
"""

import sys
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.ai_advisor import call_ai_model

logger = logging.getLogger(__name__)

DB_PATH = Path("stock_data/intel_hub.db")


class IntelligenceArchiver:
    """情报归档器"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
    
    def _load_api_key(self) -> Optional[str]:
        """加载API Key"""
        try:
            config_path = Path("user_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    settings = config.get('settings', {})
                    return settings.get('deepseek_api_key') or settings.get('kimi_api_key')
        except Exception as e:
            logger.warning(f"加载API Key失败: {e}")
        return None
    
    def compress_content(self, content: str, max_length: int = 100) -> str:
        """
        使用LLM压缩情报内容
        
        Args:
            content: 原始内容
            max_length: 最大长度
            
        Returns:
            压缩后的摘要
        """
        if len(content) <= max_length:
            return content
        
        if not self.api_key:
            # 无API Key时简单截断
            return content[:max_length] + "..."
        
        prompt = f"""请将以下金融情报压缩成{max_length}字以内的摘要，保留关键信息:

情报内容:
{content}

要求:
1. 保留日期、关键事件、影响
2. 使用简洁的语言
3. 不超过{max_length}字

直接输出摘要，不要其他内容。"""
        
        try:
            compressed, _ = call_ai_model(
                model_name="deepseek",
                specific_model="deepseek-chat",
                user_prompt=prompt,
                api_key=self.api_key,
                system_prompt="你是一个金融信息摘要助手。"
            )
            return compressed.strip()[:max_length]
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return content[:max_length] + "..."
    
    def find_archivable_intelligence(self, days: int = 180) -> List[Tuple[int, str]]:
        """
        查找需要归档的情报
        
        Args:
            days: 归档阈值天数(默认180天=6个月)
            
        Returns:
            (id, content) 列表
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 查询未归档且超过days天的情报
            cursor.execute("""
                SELECT id, content 
                FROM intelligence 
                WHERE is_archived = 0 
                AND created_at < datetime('now', '-{} days')
                AND is_active = 1
            """.format(days))
            
            results = cursor.fetchall()
            conn.close()
            
            return results
            
        except Exception as e:
            logger.error(f"查询可归档情报失败: {e}")
            return []
    
    def archive_intelligence(self, intel_id: int, content: str, 
                            dry_run: bool = False) -> bool:
        """
        归档单条情报
        
        Args:
            intel_id: 情报ID
            content: 情报内容
            dry_run: 是否仅预览
            
        Returns:
            是否成功
        """
        try:
            # 压缩内容
            summary = self.compress_content(content)
            
            if dry_run:
                print(f"  情报 {intel_id}:")
                print(f"    原长度: {len(content)} 字")
                print(f"    摘要: {summary}")
                return True
            
            # 更新数据库
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute(
                """UPDATE intelligence 
                   SET is_archived = 1, 
                       summary = ?,
                       is_active = 0
                   WHERE id = ?""",
                (summary, intel_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"情报 {intel_id} 已归档")
            return True
            
        except Exception as e:
            logger.error(f"归档情报 {intel_id} 失败: {e}")
            return False
    
    def run_archive(self, days: int = 180, dry_run: bool = False,
                   limit: Optional[int] = None) -> Dict:
        """
        执行归档任务
        
        Args:
            days: 归档阈值天数
            dry_run: 是否仅预览
            limit: 限制处理数量
            
        Returns:
            统计信息
        """
        stats = {
            'found': 0,
            'archived': 0,
            'failed': 0,
            'saved_tokens': 0
        }
        
        # 查找可归档情报
        archivable = self.find_archivable_intelligence(days)
        stats['found'] = len(archivable)
        
        if limit:
            archivable = archivable[:limit]
        
        if not archivable:
            print("✅ 没有需要归档的情报")
            return stats
        
        action = "预览" if dry_run else "归档"
        print(f"📝 发现 {len(archivable)} 条需要{action}的情报")
        
        for intel_id, content in archivable:
            original_len = len(content)
            
            if self.archive_intelligence(intel_id, content, dry_run):
                stats['archived'] += 1
                
                if not dry_run:
                    # 计算节省的token (假设1字=1token)
                    summary = self.compress_content(content)
                    saved = original_len - len(summary)
                    stats['saved_tokens'] += saved
            else:
                stats['failed'] += 1
        
        return stats
    
    def get_archive_stats(self) -> Dict:
        """获取归档统计"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 总情报数
            cursor.execute("SELECT COUNT(*) FROM intelligence")
            total = cursor.fetchone()[0]
            
            # 活跃情报数
            cursor.execute("SELECT COUNT(*) FROM intelligence WHERE is_archived = 0")
            active = cursor.fetchone()[0]
            
            # 已归档数
            cursor.execute("SELECT COUNT(*) FROM intelligence WHERE is_archived = 1")
            archived = cursor.fetchone()[0]
            
            # 6个月前的情报数
            cursor.execute("""
                SELECT COUNT(*) FROM intelligence 
                WHERE created_at < datetime('now', '-180 days')
                AND is_archived = 0
            """)
            need_archive = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total': total,
                'active': active,
                'archived': archived,
                'need_archive': need_archive,
                'archive_ratio': archived / total if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {}


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="情报归档工具")
    parser.add_argument("--dry-run", action="store_true", 
                       help="预览模式，不实际归档")
    parser.add_argument("--days", type=int, default=180,
                       help="归档阈值天数(默认180天)")
    parser.add_argument("--limit", type=int, default=None,
                       help="限制处理数量")
    parser.add_argument("--stats", action="store_true",
                       help="显示归档统计")
    
    args = parser.parse_args()
    
    archiver = IntelligenceArchiver()
    
    if args.stats:
        print("📊 归档统计")
        print("=" * 40)
        stats = archiver.get_archive_stats()
        print(f"情报总数: {stats.get('total', 0)}")
        print(f"活跃情报: {stats.get('active', 0)}")
        print(f"已归档: {stats.get('archived', 0)}")
        print(f"待归档(>6个月): {stats.get('need_archive', 0)}")
        print(f"归档比例: {stats.get('archive_ratio', 0)*100:.1f}%")
    
    else:
        print(f"🗂️ 情报归档任务")
        print("=" * 40)
        print(f"归档阈值: {args.days}天")
        print(f"模式: {'预览' if args.dry_run else '实际执行'}")
        print()
        
        stats = archiver.run_archive(
            days=args.days,
            dry_run=args.dry_run,
            limit=args.limit
        )
        
        print()
        print("📈 执行结果")
        print("-" * 40)
        print(f"发现: {stats['found']} 条")
        print(f"归档: {stats['archived']} 条")
        print(f"失败: {stats['failed']} 条")
        if stats['saved_tokens'] > 0:
            print(f"节省Token: {stats['saved_tokens']} 个")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
