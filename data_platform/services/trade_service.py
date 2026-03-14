# -*- coding: utf-8 -*-
"""
交易数据服务 - 简化版（无投资组合）

所有交易操作的唯一入口。
"""

from typing import List, Optional, Tuple
from datetime import datetime
import sqlite3

from .base_service import BaseService
from ..models.trade import TradeModel, TradeAction
from capability_platform.calculators.fee_calculator import FeeCalculator
from capability_platform.calculators.position_calculator import PositionCalculator


class TradeService(BaseService[TradeModel]):
    """
    交易服务（简化版）
    
    职责：
    1. 交易记录的增删改查
    2. 交易合法性校验（仅保留持仓检查）
    3. 交易执行（更新持仓）
    4. 费用计算
    """
    
    def get(self, trade_id: int) -> Optional[TradeModel]:
        """根据ID获取交易记录"""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM history WHERE id = ?", (trade_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return TradeModel.from_dict(dict(row))
        return None
    
    def get_all(self) -> List[TradeModel]:
        """获取所有交易记录"""
        return self.get_history(None, limit=None)
    
    def get_history(
        self, 
        symbol: Optional[str] = None, 
        limit: Optional[int] = None
    ) -> List[TradeModel]:
        """获取交易历史"""
        conn = self._get_connection()
        c = conn.cursor()
        
        if symbol:
            sql = """
                SELECT * FROM history 
                WHERE symbol = ?
                ORDER BY timestamp ASC
            """
            params = (symbol,)
        else:
            sql = """
                SELECT * FROM history 
                ORDER BY timestamp DESC
            """
            params = ()
        
        if limit:
            sql += f" LIMIT {limit}"
        
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append(TradeModel.from_dict(dict(row)))
        
        return trades
    
    def save(self, trade: TradeModel) -> Tuple[bool, str]:
        """保存交易记录"""
        valid, msg = self.validate(trade)
        if not valid:
            return False, msg
        
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO history 
                (symbol, timestamp, type, price, amount, note, fee, stamp_duty, transfer_fee)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.symbol,
                    trade.timestamp.isoformat(),
                    trade.action.value,
                    trade.price,
                    trade.amount,
                    trade.note,
                    trade.fee,
                    trade.stamp_duty,
                    trade.transfer_fee,
                )
            )
            conn.commit()
            conn.close()
            
            self.invalidate_cache()
            return True, "记录成功"
        except Exception as e:
            return False, f"记录失败: {str(e)}"
    
    def delete(self, trade_id: int) -> bool:
        """删除交易记录"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM history WHERE id = ?", (trade_id,))
            rows_affected = c.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                self.invalidate_cache()
                return True
            return False
        except Exception:
            return False
    
    def validate_trade(self, trade: TradeModel, current_shares: int = 0) -> Tuple[bool, str]:
        """校验交易合法性（简化版，仅检查持仓）"""
        # 基本校验
        valid, msg = self.validate(trade)
        if not valid:
            return False, msg
        
        # 卖出检查
        if trade.is_sell() and trade.amount > current_shares:
            return False, f"持仓不足: 当前{current_shares}股, 卖出{trade.amount}股"
        
        return True, "校验通过"
    
    def calculate_fees(self, trade: TradeModel) -> TradeModel:
        """计算交易费用"""
        fees = FeeCalculator.calculate(
            symbol=trade.symbol,
            price=trade.price,
            amount=trade.amount,
            is_sell=trade.is_sell()
        )
        
        return TradeModel(
            id=trade.id,
            symbol=trade.symbol,
            action=trade.action,
            price=trade.price,
            amount=trade.amount,
            timestamp=trade.timestamp,
            fee=fees['fee'],
            stamp_duty=fees['stamp_duty'],
            transfer_fee=fees['transfer_fee'],
            note=trade.note,
        )
    
    def execute(self, trade: TradeModel, auto_save: bool = True) -> Tuple[bool, str, Optional[dict]]:
        """
        执行交易
        
        流程：
        1. 校验交易
        2. 计算费用
        3. 获取当前持仓
        4. 计算新持仓
        5. 保存交易记录
        6. 更新持仓
        """
        from .position_service import PositionService
        
        # 1. 获取当前持仓
        position_service = PositionService()
        current_position = position_service.get(trade.symbol)
        current_shares = current_position.shares if current_position else 0
        current_cost = current_position.cost if current_position else 0.0
        base_shares = current_position.base_shares if current_position else 0
        
        # 2. 校验交易
        valid, msg = self.validate_trade(trade, current_shares)
        if not valid:
            return False, msg, None
        
        # 3. 计算费用
        trade_with_fees = self.calculate_fees(trade)
        
        # 4. 计算新持仓
        if trade.action.affects_position():
            new_shares, new_cost = PositionCalculator.calculate_new_position(
                current_shares=current_shares,
                current_cost=current_cost,
                action=trade.action,
                trade_price=trade.price,
                trade_amount=trade.amount
            )
        else:
            new_shares, new_cost = current_shares, current_cost
            if trade.action == TradeAction.BASE_POSITION:
                base_shares = trade.amount
        
        # 5. 保存交易记录
        if auto_save:
            success, msg = self.save(trade_with_fees)
            if not success:
                return False, f"交易记录失败: {msg}", None
        
        # 6. 更新持仓
        if trade.action.affects_position():
            from ..models.position import PositionModel
            new_position = PositionModel(
                symbol=trade.symbol,
                shares=new_shares,
                cost=new_cost,
                base_shares=base_shares,
            )
            success, msg = position_service.save(new_position)
            if not success:
                return False, f"持仓更新失败: {msg}", None
        
        return True, "交易执行成功", {
            'trade': trade_with_fees,
            'old_position': current_position,
            'new_shares': new_shares,
            'new_cost': new_cost,
        }
