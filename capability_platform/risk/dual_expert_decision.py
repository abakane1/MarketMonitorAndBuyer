# -*- coding: utf-8 -*-
"""
双专家风控决策模块 (Dual Expert Decision)

v4.1.0 Week 2 - Dual-Expert Architecture Phase 1
功能:
1. 红蓝专家决策矩阵
2. 风险评分拦截逻辑
3. 强制风控规则执行

Author: AI Programmer
Date: 2026-03-14
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class Decision(Enum):
    """决策结果"""
    APPROVE = "approve"      # 通过
    CAUTION = "caution"      # 谨慎
    REJECT = "reject"        # 拒绝


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"              # 低风险
    MEDIUM = "medium"        # 中风险
    HIGH = "high"            # 高风险


@dataclass
class BlueAdvice:
    """蓝军(DeepSeek)建议"""
    action: str              # buy/sell/hold
    confidence: float        # 置信度 0-1
    reasoning: str           # 推理过程
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class RedAudit:
    """红军(Gemini)审计结果"""
    risk_score: float        # 风险评分 0-10
    critical_flaws: List[str]  # 致命缺陷
    concerns: List[str]      # 关注点
    recommendation: str      # 建议


@dataclass
class DualExpertDecision:
    """双专家决策结果"""
    decision: Decision       # 最终决策
    risk_level: RiskLevel    # 风险等级
    blue_advice: BlueAdvice
    red_audit: RedAudit
    execution_allowed: bool  # 是否允许执行
    warning_message: str     # 警告信息


class DualExpertDecisionEngine:
    """
    双专家决策引擎
    
    根据红蓝专家的意见，做出最终决策
    
    决策矩阵:
    | Blue Action | Red Score | Decision      | Execution |
    |-------------|-----------|---------------|-----------|
    | Buy         | < 4       | Strong Buy    | ✅        |
    | Buy         | 4-7       | Cautious Buy  | ⚠️        |
    | Buy         | > 7       | Reject        | ❌        |
    | Sell/Hold   | Any       | Wait          | ⏸️        |
    """
    
    def __init__(self):
        # 可配置的风控阈值
        self.risk_threshold_low = 4.0      # 低风险阈值
        self.risk_threshold_high = 7.0     # 高风险阈值
        self.min_blue_confidence = 0.6     # 蓝军最低置信度
    
    def evaluate(self, blue: BlueAdvice, red: RedAudit) -> DualExpertDecision:
        """
        评估双专家意见，做出决策
        
        Args:
            blue: 蓝军建议
            red: 红军审计
            
        Returns:
            决策结果
        """
        # 1. 确定风险等级
        risk_level = self._determine_risk_level(red.risk_score)
        
        # 2. 应用决策矩阵
        decision, execution_allowed, warning = self._apply_decision_matrix(
            blue.action, red.risk_score, blue.confidence
        )
        
        # 3. 额外风控检查
        if blue.confidence < self.min_blue_confidence:
            decision = Decision.CAUTION
            execution_allowed = False
            warning = f"蓝军置信度不足({blue.confidence:.0%})，建议观望"
        
        # 4. 红军致命缺陷检查
        if red.critical_flaws:
            decision = Decision.REJECT
            execution_allowed = False
            warning = f"红军发现致命缺陷: {red.critical_flaws[0]}"
        
        return DualExpertDecision(
            decision=decision,
            risk_level=risk_level,
            blue_advice=blue,
            red_audit=red,
            execution_allowed=execution_allowed,
            warning_message=warning
        )
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """确定风险等级"""
        if risk_score < self.risk_threshold_low:
            return RiskLevel.LOW
        elif risk_score < self.risk_threshold_high:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH
    
    def _apply_decision_matrix(self, blue_action: str, red_score: float,
                               blue_confidence: float) -> tuple:
        """
        应用决策矩阵
        
        Returns:
            (decision, execution_allowed, warning_message)
        """
        action = blue_action.lower()
        
        # 卖出或观望直接通过
        if action in ['sell', 'hold', '观望', '卖出']:
            return (
                Decision.APPROVE,
                True,
                "蓝军建议观望/卖出，无需红军审批"
            )
        
        # 买入需要红军审批
        if action in ['buy', '买入']:
            if red_score < self.risk_threshold_low:
                return (
                    Decision.APPROVE,
                    True,
                    "✅ 强力买入 - 蓝军看多且红军风险可控"
                )
            elif red_score < self.risk_threshold_high:
                return (
                    Decision.CAUTION,
                    False,  # 默认不允许执行，需要人工确认
                    f"⚠️ 谨慎买入 - 红军风险评分{red_score:.1f}，建议降低仓位"
                )
            else:
                return (
                    Decision.REJECT,
                    False,
                    f"🛑 拒绝买入 - 红军风险评分{red_score:.1f}，风险过高"
                )
        
        # 未知操作
        return (
            Decision.CAUTION,
            False,
            f"⚠️ 未知操作建议: {blue_action}"
        )
    
    def format_decision_report(self, result: DualExpertDecision) -> str:
        """
        格式化决策报告
        
        Args:
            result: 决策结果
            
        Returns:
            格式化报告
        """
        lines = []
        lines.append("⚔️ 双专家决策报告")
        lines.append("=" * 50)
        
        # 蓝军建议
        lines.append("\n🔵 蓝军 (DeepSeek) 建议:")
        lines.append(f"  操作: {result.blue_advice.action.upper()}")
        lines.append(f"  置信度: {result.blue_advice.confidence:.0%}")
        if result.blue_advice.entry_price:
            lines.append(f"  建议价格: {result.blue_advice.entry_price}")
        if result.blue_advice.stop_loss:
            lines.append(f"  止损位: {result.blue_advice.stop_loss}")
        
        # 红军审计
        lines.append("\n🔴 红军 (Gemini) 审计:")
        lines.append(f"  风险评分: {result.red_audit.risk_score:.1f}/10")
        lines.append(f"  风险等级: {result.risk_level.value.upper()}")
        if result.red_audit.critical_flaws:
            lines.append(f"  致命缺陷: {', '.join(result.red_audit.critical_flaws)}")
        if result.red_audit.concerns:
            lines.append(f"  关注点: {', '.join(result.red_audit.concerns[:3])}")
        
        # 决策结果
        decision_emoji = {
            Decision.APPROVE: "✅",
            Decision.CAUTION: "⚠️",
            Decision.REJECT: "🛑"
        }
        
        lines.append("\n📋 最终决策:")
        lines.append(f"  {decision_emoji[result.decision]} {result.decision.value.upper()}")
        lines.append(f"  执行权限: {'✅ 允许' if result.execution_allowed else '❌ 禁止'}")
        lines.append(f"  提示: {result.warning_message}")
        
        return "\n".join(lines)


# 便捷函数
def evaluate_trade_decision(blue_action: str, blue_confidence: float,
                           red_score: float, red_flaws: Optional[List[str]] = None) -> Dict:
    """
    快速评估交易决策
    
    Args:
        blue_action: 蓝军建议操作
        blue_confidence: 蓝军置信度
        red_score: 红军风险评分
        red_flaws: 红军发现的缺陷
        
    Returns:
        简化决策结果
    """
    engine = DualExpertDecisionEngine()
    
    blue = BlueAdvice(
        action=blue_action,
        confidence=blue_confidence,
        reasoning=""
    )
    
    red = RedAudit(
        risk_score=red_score,
        critical_flaws=red_flaws or [],
        concerns=[],
        recommendation=""
    )
    
    result = engine.evaluate(blue, red)
    
    return {
        'decision': result.decision.value,
        'risk_level': result.risk_level.value,
        'execution_allowed': result.execution_allowed,
        'warning': result.warning_message
    }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    engine = DualExpertDecisionEngine()
    
    # 测试场景1: 强力买入
    blue1 = BlueAdvice("buy", 0.85, "技术面突破")
    red1 = RedAudit(3.0, [], ["市场波动"], "风险可控")
    result1 = engine.evaluate(blue1, red1)
    print(engine.format_decision_report(result1))
    print("\n" + "=" * 50 + "\n")
    
    # 测试场景2: 拒绝买入
    blue2 = BlueAdvice("buy", 0.75, "业绩预增")
    red2 = RedAudit(8.5, ["流动性风险"], ["大盘不稳", "行业逆风"], "建议观望")
    result2 = engine.evaluate(blue2, red2)
    print(engine.format_decision_report(result2))
