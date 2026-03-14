# -*- coding: utf-8 -*-
"""
持仓数据服务 - 简化版（无投资组合）

所有持仓操作的唯一入口。
"""

from typing import List, Optional, Tuple
import sqlite3

from .base_service import BaseService
from ..models.position import PositionModel
from capability_platform.calculators.position_calculator import PositionCalculator


class PositionService(BaseService[PositionModel]):
    """
    持仓服务（简化版）
    
    职责：
    1. 持仓数据的增删改查
    2. 持仓的重新计算
    3. 持仓一致性保障
    """
    
    def get(self, symbol: str) -> Optional[PositionModel]:
        """获取持仓"""
        cached = self._get_from_cache(symbol)
        if cached:
            return cached
        
        conn = self._get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT symbol, shares, cost, base_shares FROM positions WHERE symbol = ?",
            (symbol,)
        )
        row = c.fetchone()
        conn.close()
        
        if row:
            position = PositionModel(
                symbol=row['symbol'],
                shares=row['shares'],
                cost=row['cost'],
                base_shares=row['base_shares'] if row['base_shares'] else 0,
            )
            self._set_cache(symbol, position)
            return position
        
        return None
    
    def get_all(self) -> List[PositionModel]:
        """获取所有持仓"""
        cache_key = "all_positions"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        conn = self._get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT symbol, shares, cost, base_shares FROM positions WHERE shares > 0"
        )
        rows = c.fetchall()
        conn.close()
        
        positions = []
        for row in rows:
            positions.append(PositionModel(
                symbol=row['symbol'],
                shares=row['shares'],
                cost=row['cost'],
                base_shares=row['base_shares'] if row['base_shares'] else 0,
            ))
        
        self._set_cache(cache_key, positions)
        return positions
    
    def save(self, position: PositionModel) -> Tuple[bool, str]:
        """保存持仓"""
        valid, msg = self.validate(position)
        if not valid:
            return False, msg
        
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO positions (symbol, name, shares, cost, base_shares)
                VALUES (?, COALESCE((SELECT name FROM positions WHERE symbol = ?), ''), ?, ?, ?)
                """,
                (position.symbol, position.symbol, position.shares, position.cost, position.base_shares)
            )
            conn.commit()
            conn.close()
            
            # 清除缓存
            self.invalidate_cache(position.symbol)
            self.invalidate_cache("all_positions")
            
            return True, "保存成功"
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    def delete(self, symbol: str) -> bool:
        """删除持仓"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
            conn.commit()
            conn.close()
            
            self.invalidate_cache(symbol)
            self.invalidate_cache("all_positions")
            
            return True
        except Exception:
            return False
    
    def recalculate_from_history(self, symbol: str) -> Optional[PositionModel]:
        """从交易历史重新计算持仓"""
        from .trade_service import TradeService
        
        trade_service = TradeService()
        trades = trade_service.get_history(symbol)
        
        new_shares, new_cost, base_shares = PositionCalculator.recalculate_from_trades(trades)
        
        position = PositionModel(
            symbol=symbol,
            shares=new_shares,
            cost=new_cost,
            base_shares=base_shares,
        )
        
        self.save(position)
        return position
    
    def update_base_shares(self, symbol: str, base_shares: int) -> Tuple[bool, str]:
        """更新底仓"""
        position = self.get(symbol)
        if not position:
            return False, "持仓不存在"
        
        if base_shares > position.shares:
            return False, f"底仓({base_shares})不能超过持仓({position.shares})"
        
        new_position = position.with_base_shares(base_shares)
        return self.save(new_position)
    
    def get_position_with_quote(self, symbol: str, quote_service=None) -> Optional[dict]:
        """获取持仓及实时行情"""
        position = self.get(symbol)
        if not position:
            return None
        
        result = {
            'position': position,
            'quote': None,
            'market_value': 0.0,
            'floating_pnl': 0.0,
            'today_pnl': 0.0,
        }
        
        if quote_service:
            quote = quote_service.get_realtime(symbol)
            if quote:
                result['quote'] = quote
                result['market_value'] = position.market_value(quote.price)
                result['floating_pnl'] = position.floating_pnl(quote.price)
                result['today_pnl'] = position.today_pnl(quote.price, quote.pre_close)
        
        return result
