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
from utils.legion_advisor import run_blue_legion, run_red_legion

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
    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> Tuple[str, str]:
        """
        Audits a strategy proposal.
        Returns: (audit_content, debug_prompt)
        """
        pass
    
    @abstractmethod
    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, str]:
        """
        Refines a strategy based on audit.
        Returns: (content, reasoning, debug_prompt)
        """
        pass
    
    @abstractmethod
    def decide(self, aggregated_history: list, prompt_templates: Dict[str, str], context_data: Dict[str, Any] = None, **kwargs) -> Tuple[str, str, str]:
        """
        Makes the final decision based on aggregated history.
        Returns: (content, reasoning, debug_prompt)
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

    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> Tuple[str, str]:
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
        
        full_prompt = f"System: {sys_p}\n\nUser: {user_p}"
        
        if not self.api_key:
            return "Error: Missing DeepSeek API Key", full_prompt
            
        content, reasoning = call_deepseek_api(self.api_key, sys_p, user_p)
        return content, full_prompt

    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, str]:
        """
        Refines strategy.
        """
        sys_p, user_p = build_refinement_prompt(
            original_context, original_plan, audit_report, prompt_templates
        )
        
        full_prompt = f"System: {sys_p}\n\nUser: {user_p}"
        
        if not self.api_key:
            return "Error: Missing DeepSeek API Key", "", full_prompt
            
        c, r = call_deepseek_api(self.api_key, sys_p, user_p)
        return c, r, full_prompt

    def decide(self, aggregated_history: list, prompt_templates: Dict[str, str], context_data: Dict[str, Any] = None, **kwargs) -> Tuple[str, str, str]:
        """
        Sign Final Order.
        """
        sys_p, user_p = build_final_decision_prompt(aggregated_history, prompt_templates, context_data=context_data)
        
        full_prompt = f"System: {sys_p}\n\nUser: {user_p}"
        
        if not self.api_key:
             return "Error: Missing DeepSeek API Key", "", full_prompt
             
        c, r = call_deepseek_api(self.api_key, sys_p, user_p)
        return c, r, full_prompt


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

    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> Tuple[str, str]:
        """
        Conducts Audit using Qwen Red Legion (MoE).
        """
        # Inject raw context for Red Legion if needed
        audit_ctx = context_data.copy()
        if 'daily_stats' not in audit_ctx and 'raw_context' in kwargs:
             audit_ctx['daily_stats'] = kwargs['raw_context']
        if 'research_context' not in audit_ctx and 'research_context' in kwargs:
             audit_ctx['research_context'] = kwargs['research_context']
             
        if not self.api_key:
             return "Error: Missing Qwen API Key", "No Prompt (Legion Mode)"

        # Run Red Legion
        final_res, full_log = run_red_legion(audit_ctx, plan_content, self.api_key, prompt_templates)
        
        return final_res, full_log

    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, str]:
        sys_p, user_p = build_refinement_prompt(
            original_context, original_plan, audit_report, prompt_templates
        )
        
        full_prompt = f"System: {sys_p}\n\nUser: {user_p}"
        
        if not self.api_key:
             return "Error: Missing Qwen API Key", "", full_prompt
        
        # Qwen doesn't return separate reasoning, so reasoning is empty str
        content = call_qwen_api(self.api_key, sys_p, user_p)
        return content, "", full_prompt

    def decide(self, aggregated_history: list, prompt_templates: Dict[str, str], context_data: Dict[str, Any] = None, **kwargs) -> Tuple[str, str, str]:
        sys_p, user_p = build_final_decision_prompt(aggregated_history, prompt_templates, context_data=context_data)
        
        full_prompt = f"System: {sys_p}\n\nUser: {user_p}"
        
        if not self.api_key:
             return "Error: Missing Qwen API Key", "", full_prompt
             
        content = call_qwen_api(self.api_key, sys_p, user_p)
        return content, "", full_prompt



class KimiExpert(BaseExpert):
    """
    Expert wrapper for Kimi (Moonshot AI).
    Responsible for Red Legion Audit.
    """
    def __init__(self, api_key: str, base_url: str = None, model_name: str = "kimi-k2.5"):
        super().__init__("Kimi", api_key)
        self.base_url = base_url
        self.model_name = model_name

    def propose(self, context_data: Dict[str, Any], prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, Any, Any]:
        return "Kimi Proposer Not Implemented", "", "", []

    def audit(self, context_data: Dict[str, Any], plan_content: str, prompt_templates: Dict[str, str], is_final: bool = False, **kwargs) -> Tuple[str, str]:
        """
        Conducts Audit using Kimi Red Legion (MoE).
        """
        audit_ctx = context_data.copy()
        if 'daily_stats' not in audit_ctx and 'raw_context' in kwargs:
             audit_ctx['daily_stats'] = kwargs['raw_context']
        if 'research_context' not in audit_ctx and 'research_context' in kwargs:
             audit_ctx['research_context'] = kwargs['research_context']
             
        if not self.api_key:
             return "Error: Missing Kimi API Key", "No Prompt"

        # Use Kimi 2.5 (MoE Architecture)
        final_res, full_log = run_red_legion(
            audit_ctx, 
            plan_content, 
            self.api_key, 
            prompt_templates, 
            model_type="kimi", 
            model_name=self.model_name,
            is_final=is_final,
            kimi_base_url=self.base_url
        )
        
        return final_res, full_log

    def refine(self, original_context: str, original_plan: str, audit_report: str, prompt_templates: Dict[str, str], **kwargs) -> Tuple[str, str, str]:
        return "Kimi Refine Not Implemented", "", ""

    def decide(self, aggregated_history: list, prompt_templates: Dict[str, str], context_data: Dict[str, Any] = None, **kwargs) -> Tuple[str, str, str]:
        return "Kimi Decide Not Implemented", "", ""


class ExpertRegistry:
    """
    Factory to get experts.
    """
    @staticmethod
    def get_expert(name: str, api_keys: Dict[str, str]) -> Optional[BaseExpert]:
        """
        Returns an instance of the requested expert.
        """
        name_lower = name.lower()
        if name_lower == "deepseek":
            return DeepSeekExpert(api_keys.get("deepseek_api_key", ""))
        elif name_lower == "qwen":
            return QwenExpert(api_keys.get("qwen_api_key", ""))
        elif name_lower == "kimi":
            # Extract base_url if present in api_keys or fallback to None
            k_base = api_keys.get("kimi_base_url")
            # Explicitly pass the compatible model name
            return KimiExpert(api_key=api_keys.get("kimi_api_key", ""), base_url=k_base or "", model_name="kimi-k2.5")
        else:
            return None
