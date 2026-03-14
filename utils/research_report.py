# -*- coding: utf-8 -*-
"""
Research Report Data Model - 研报记录数据模型 v2.1
重构目标: 清晰分离每一步的提示词、思考过程、决策内容
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class StepType(Enum):
    """步骤类型"""
    DRAFT = "draft"           # 蓝军初稿
    AUDIT1 = "audit1"         # 红军初审
    REFINE = "refine"         # 蓝军优化
    AUDIT2 = "audit2"         # 红军终审
    FINAL = "final"           # 最终执行令


@dataclass
class StepRecord:
    """单步记录 - 存储每一步的完整信息"""
    step: int                          # 步骤序号 1-5
    step_type: str                     # 步骤类型
    role: str                          # 角色名称 (如: 蓝军主帅)
    model: str                         # 使用的模型
    
    # 输入部分
    system_prompt: str                 # System Prompt
    user_prompt: str                   # User Prompt
    
    # 输出部分
    reasoning: str = ""                # 思考过程 (CoT)
    content: str = ""                  # 大模型决策内容
    decision: Optional[str] = None     # 决策结果 (用于有明确裁决的步骤)
    
    # 元数据
    timestamp: Optional[str] = None    # 该步骤生成时间
    duration_ms: Optional[int] = None  # 耗时
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step": self.step,
            "step_type": self.step_type,
            "role": self.role,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "reasoning": self.reasoning,
            "content": self.content,
            "decision": self.decision,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StepRecord':
        """从字典创建"""
        return cls(**data)


@dataclass
class FinalDecision:
    """最终决策摘要 - 提取的关键信息"""
    direction: str = ""        # 方向: 买入/卖出/观望
    price: str = ""            # 建议价格
    shares: str = ""           # 建议股数
    stop_loss: str = ""        # 止损价格
    take_profit: str = ""      # 止盈价格
    mode: str = ""             # 交易模式
    notes: str = ""            # 备注
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FinalDecision':
        return cls(**data)


@dataclass
class ResearchReport:
    """
    研报记录主类 - 结构化存储五步MoE工作流的所有数据
    """
    # 基本信息
    symbol: str                        # 股票代码
    timestamp: str                     # 生成时间
    version: str = "2.1"               # 数据版本
    
    # 工作流步骤 (1-5步)
    steps: List[StepRecord] = None
    
    # 最终决策摘要
    final_decision: Optional[FinalDecision] = None
    
    # 执行追踪
    execution_result: Optional[Dict] = None  # 实际执行结果
    
    # 原始兼容性字段 (用于向后兼容)
    raw_result: Optional[str] = None   # 原始result字符串
    raw_prompt: Optional[str] = None   # 原始prompt字符串
    raw_reasoning: Optional[str] = None # 原始reasoning字符串
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
    
    def add_step(self, step: StepRecord):
        """添加步骤记录"""
        self.steps.append(step)
    
    def get_step(self, step_type: str) -> Optional[StepRecord]:
        """获取指定类型的步骤"""
        for step in self.steps:
            if step.step_type == step_type:
                return step
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (用于JSON序列化)"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "final_decision": self.final_decision.to_dict() if self.final_decision else None,
            "execution_result": self.execution_result,
            # 兼容性字段
            "raw_result": self.raw_result,
            "raw_prompt": self.raw_prompt,
            "raw_reasoning": self.raw_reasoning
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchReport':
        """从字典创建"""
        steps = [StepRecord.from_dict(s) for s in data.get("steps", [])]
        final_decision = None
        if data.get("final_decision"):
            final_decision = FinalDecision.from_dict(data["final_decision"])
        
        return cls(
            symbol=data.get("symbol", ""),
            timestamp=data.get("timestamp", ""),
            version=data.get("version", "2.1"),
            steps=steps,
            final_decision=final_decision,
            execution_result=data.get("execution_result"),
            raw_result=data.get("raw_result"),
            raw_prompt=data.get("raw_prompt"),
            raw_reasoning=data.get("raw_reasoning")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ResearchReport':
        """从JSON字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_legacy_log(cls, log: Dict[str, Any]) -> 'ResearchReport':
        """
        从旧的日志格式迁移到新的结构化格式
        这是兼容性方法，用于处理历史数据
        """
        symbol = log.get("symbol", "")
        timestamp = log.get("timestamp", "")
        
        report = cls(
            symbol=symbol,
            timestamp=timestamp,
            raw_result=log.get("result"),
            raw_prompt=log.get("prompt"),
            raw_reasoning=log.get("reasoning")
        )
        
        # 尝试从details解析结构化数据
        details_str = log.get("details", "")
        if details_str:
            try:
                details = json.loads(details_str)
                if "steps" in details:
                    # 已经是新格式
                    report.steps = [StepRecord.from_dict(s) for s in details["steps"]]
                    if details.get("final_decision"):
                        report.final_decision = FinalDecision.from_dict(details["final_decision"])
                    return report
                
                # 从旧格式的prompts_history迁移
                ph = details.get("prompts_history", {})
                
                # 尝试从result字符串解析各步骤内容
                result = log.get("result", "")
                
                # 解析步骤内容
                step_contents = cls._parse_legacy_result(result)
                
                # 构建步骤记录
                step_mapping = [
                    ("draft", "蓝军初稿", 1),
                    ("audit1", "红军初审", 2),
                    ("refine", "蓝军优化", 3),
                    ("audit2", "红军终审", 4),
                    ("final", "最终执行", 5)
                ]
                
                for step_type, role, step_num in step_mapping:
                    # 获取该步骤的prompt
                    sys_key = f"{step_type}_sys"
                    user_key = f"{step_type}_user"
                    
                    system_prompt = ph.get(sys_key, "")
                    user_prompt = ph.get(user_key, "")
                    
                    # 如果找不到分开的prompt，尝试合并的key
                    if not system_prompt and not user_prompt:
                        combined = ph.get(step_type, "")
                        if combined:
                            # 尝试分割system和user
                            if "System" in combined and "User" in combined:
                                parts = combined.split("User")
                                if len(parts) >= 2:
                                    system_prompt = parts[0].replace("System", "").strip()
                                    user_prompt = "User" + parts[1] if len(parts) == 2 else "User".join(parts[1:])
                    
                    content = step_contents.get(step_type, "")
                    
                    if system_prompt or user_prompt or content:
                        step_record = StepRecord(
                            step=step_num,
                            step_type=step_type,
                            role=role,
                            model=log.get("model", "DeepSeek"),
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            content=content,
                            reasoning=""  # 旧格式reasoning是合并的，无法分离
                        )
                        report.add_step(step_record)
                
            except Exception as e:
                print(f"Error migrating legacy log: {e}")
        
        return report
    
    @staticmethod
    def _parse_legacy_result(result: str) -> Dict[str, str]:
        """从旧的result字符串解析各步骤内容"""
        contents = {}
        
        # 定义标记
        markers = {
            'draft': ["--- 📜 v1.0 Draft ---", "v1.0 Draft"],
            'audit1': ["--- 🔴 Round 1 Audit ---", "Round 1 Audit"],
            'refine': ["--- 🔄 v2.0 Refined ---", "v2.0 Refined"],
            'audit2': ["--- ⚖️ Final Verdict ---", "Final Verdict"],
            'final': ["[Final Execution Order]", "Final Execution", "Final Decision"]
        }
        
        if not result:
            return contents
        
        # 找到第一个标记之前的内容是最终决策
        first_marker_pos = len(result)
        for step_type, marker_list in markers.items():
            for marker in marker_list:
                pos = result.find(marker)
                if pos != -1 and pos < first_marker_pos:
                    first_marker_pos = pos
        
        # 第一个标记之前的内容就是最终决策 (Final Execution Order)
        if first_marker_pos > 0:
            contents['final'] = result[:first_marker_pos].strip()
        else:
            # 没有找到任何标记，整个内容就是最终决策
            contents['final'] = result.strip()
        
        # 解析各步骤 (从标记之后的内容)
        for step_type, marker_list in markers.items():
            for marker in marker_list:
                if marker in result:
                    start = result.find(marker) + len(marker)
                    # 找到下一个标记
                    end = len(result)
                    for other_step, other_markers in markers.items():
                        if other_step != step_type:
                            for other_marker in other_markers:
                                pos = result.find(other_marker, start)
                                if pos != -1 and pos < end:
                                    end = pos
                    contents[step_type] = result[start:end].strip()
                    break
        
        return contents


def create_report_from_workflow(
    symbol: str,
    workflow_steps: List[Dict[str, Any]],
    blue_model: str = "DeepSeek",
    red_model: str = "Kimi"
) -> ResearchReport:
    """
    从工作流步骤创建研报记录
    
    Args:
        symbol: 股票代码
        workflow_steps: 工作流步骤数据列表
        blue_model: 蓝军模型
        red_model: 红军模型
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = ResearchReport(symbol=symbol, timestamp=timestamp)
    
    # 步骤角色映射
    role_mapping = {
        "draft": ("蓝军初稿", blue_model),
        "audit1": ("红军初审", red_model),
        "refine": ("蓝军优化", blue_model),
        "audit2": ("红军终审", red_model),
        "final": ("最终执行", blue_model)
    }
    
    for i, step_data in enumerate(workflow_steps, 1):
        step_type = step_data.get("step_type", f"step_{i}")
        role, model = role_mapping.get(step_type, ("未知", "Unknown"))
        
        step_record = StepRecord(
            step=i,
            step_type=step_type,
            role=role,
            model=model,
            system_prompt=step_data.get("system_prompt", ""),
            user_prompt=step_data.get("user_prompt", ""),
            reasoning=step_data.get("reasoning", ""),
            content=step_data.get("content", ""),
            decision=step_data.get("decision"),
            timestamp=step_data.get("timestamp"),
            duration_ms=step_data.get("duration_ms")
        )
        report.add_step(step_record)
    
    return report
