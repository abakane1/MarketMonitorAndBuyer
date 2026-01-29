# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
import json

# Import existing logic to reuse
from utils.ai_advisor import (
    call_deepseek_api, 
    ask_deepseek_advisor,
    build_advisor_prompt,
    build_red_team_prompt,
    build_refinement_prompt,
    build_final_decision_prompt,
    call_qwen_api
)
from utils.legion_advisor import run_blue_legion

class BaseExpert(ABC):
    """
    Abstract Base Class for all AI Experts (Models).
    Standardizes the interface for Propose, Audit, and Refine actions.
    """
    def __init__(self, name: str, api_key: str):
        self.name = name
        self.api_key = api_key

    @abstractmethod
    def propose(self, context_data: Dict[str, Any], prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, Any, Any]:
        """
        Generates a strategy proposal.
        Returns: (content, reasoning, debug_prompt, extra_logs)
        """
        pass

    @abstractmethod
    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> str:
        """
        Audits a strategy proposal.
        Returns: audit_content
        """
        pass
    
    @abstractmethod
    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        """
        Refines a strategy based on audit.
        Returns: (content, reasoning)
        """
        pass
    
    @abstractmethod
    def decide(self, final_verdict: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        """
        Makes the final decision based on final verdict.
        Returns: (content, reasoning)
        """
        pass

class DeepSeekExpert(BaseExpert):
    """
    Expert wrapper for DeepSeek Reasoner (R1).
    Strong at Reasoning and Audit.
    """
    def __init__(self, api_key: str):
        super().__init__("DeepSeek", api_key)

    def propose(self, context_data: Dict[str, Any], prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, Any, Any]:
        """
        Uses standard ask_deepseek_advisor logic.
        """
        # kwargs can contain 'research_context', 'technical_indicators', etc.
        research_context = kwargs.get('research_context', "")
        
        # Call legacy wrapper
        content, reasoning, user_prompt = ask_deepseek_advisor(
            self.api_key, 
            context_data, 
            research_context=research_context,
            technical_indicators=kwargs.get('technical_indicators'),
            fund_flow_data=kwargs.get('fund_flow_data'),
            fund_flow_history=kwargs.get('fund_flow_history'),
            intraday_summary=kwargs.get('intraday_summary'),
            prompt_templates=prompt_templates,
            suffix_key=kwargs.get('suffix_key', "deepseek_research_suffix"),
            symbol=context_data.get('code')
        )
        return content, reasoning, user_prompt, None

    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> str:
        """
        Conducts Red Team Audit.
        """
        # Construct audit context
        audit_ctx = context_data.copy()
        audit_ctx['deepseek_plan'] = plan_content
        # Ensure dailystats/bg_info is present
        if 'daily_stats' not in audit_ctx and 'raw_context' in kwargs:
             audit_ctx['daily_stats'] = kwargs['raw_context']
             
        # Build prompt
        sys_p, user_p = build_red_team_prompt(
            audit_ctx, 
            prompt_templates, 
            is_final_round=is_final
        )
        
        if not self.api_key:
            return "Error: Missing DeepSeek API Key"
            
        content, reasoning = call_deepseek_api(self.api_key, sys_p, user_p)
        return content

    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        """
        Refines strategy.
        """
        sys_p, user_p = build_refinement_prompt(
            original_context, original_plan, audit_report, prompt_templates
        )
        
        if not self.api_key:
            return "Error: Missing DeepSeek API Key", ""
            
        return call_deepseek_api(self.api_key, sys_p, user_p)

    def decide(self, final_verdict: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        """
        Sign Final Order.
        """
        sys_p, user_p = build_final_decision_prompt(final_verdict, prompt_templates)
        
        if not self.api_key:
             return "Error: Missing DeepSeek API Key", ""
             
        return call_deepseek_api(self.api_key, sys_p, user_p)


class QwenExpert(BaseExpert):
    """
    Expert wrapper for Qwen (Tongyi Qianwen).
    Strong at Strategy Formation (MoE) and Synthesis.
    """
    def __init__(self, api_key: str):
        super().__init__("Qwen", api_key)

    def propose(self, context_data: Dict[str, Any], prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, Any, Any]:
        """
        Uses Blue Legion (MoE) logic.
        """
        code = context_data.get('code')
        name = context_data.get('name')
        price = context_data.get('price')
        
        # Inject standard data into context_data for sub-agents if needed
        # run_blue_legion handles extracting 'intraday_summary', 'capital_flow_str' from context_data
        # so we need to ensure context_data has these keys populated.
        
        # Helper to populate context if missing
        if 'intraday_summary' not in context_data and kwargs.get('intraday_summary'):
            context_data['intraday_summary'] = kwargs['intraday_summary']
            
        # Capital flow might be in kwargs
        # We need to format it if not present?
        # For now, assume caller (lab.py or strategy_section.py) has prepared context_data mostly.
        
        final_res, legion_reasoning, cmd_prompt, logs = run_blue_legion(
            code, name, price, self.api_key, context_data, prompt_templates
        )
        return final_res, legion_reasoning, cmd_prompt, logs

    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> str:
        """
        Conducts Audit using Qwen.
        """
        audit_ctx = context_data.copy()
        audit_ctx['deepseek_plan'] = plan_content
        if 'daily_stats' not in audit_ctx and 'raw_context' in kwargs:
             audit_ctx['daily_stats'] = kwargs['raw_context']
             
        sys_p, user_p = build_red_team_prompt(
            audit_ctx, 
            prompt_templates, 
            is_final_round=is_final
        )
        
        if not self.api_key:
             return "Error: Missing Qwen API Key"
             
        # Use simple call_qwen_api wrapper
        return call_qwen_api(self.api_key, sys_p, user_p)

    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        sys_p, user_p = build_refinement_prompt(
            original_context, original_plan, audit_report, prompt_templates
        )
        if not self.api_key:
             return "Error: Missing Qwen API Key", ""
        
        # Qwen doesn't return separate reasoning, so reasoning is empty str
        content = call_qwen_api(self.api_key, sys_p, user_p)
        return content, ""

    def decide(self, final_verdict: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str]:
        sys_p, user_p = build_final_decision_prompt(final_verdict, prompt_templates)
        
        if not self.api_key:
             return "Error: Missing Qwen API Key", ""
             
        content = call_qwen_api(self.api_key, sys_p, user_p)
        return content, ""


class ExpertRegistry:
    """
    Factory to get experts.
    """
    @staticmethod
    def get_expert(name: str, api_keys: Dict[str, str]) -> Optional[BaseExpert]:
        """
        Returns an instance of the requested expert.
        """
        if name.lower() == "deepseek":
            return DeepSeekExpert(api_keys.get("deepseek_api_key", ""))
        elif name.lower() == "qwen":
            return QwenExpert(api_keys.get("qwen_api_key", ""))
        else:
            return None
