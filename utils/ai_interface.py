# -*- coding: utf-8 -*-
"""
AI接口统一模块 (AI Interface)

v4.1.0 Week 3 - Dual-Expert Architecture Phase 2
功能:
1. 统一Web界面和命令行的AI调用
2. 消除skill与人工操作差异
3. 提供一致的API调用体验

Author: AI Programmer
Date: 2026-03-14
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

from utils.ai_advisor import call_ai_model, call_deepseek_api, call_kimi_api

logger = logging.getLogger(__name__)


@dataclass
class AIRequest:
    """AI请求"""
    model_name: str              # deepseek/kimi/qwen
    user_prompt: str
    system_prompt: str = ""
    specific_model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@dataclass
class AIResponse:
    """AI响应"""
    content: str
    reasoning: str
    model: str
    success: bool
    error_message: Optional[str] = None


class UnifiedAIInterface:
    """
    统一AI接口
    
    Web界面和命令行使用相同的调用方式
    """
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            config_path = Path("user_config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('settings', {})
        except Exception as e:
            logger.warning(f"加载配置失败: {e}")
        return {}
    
    def _get_api_key(self, model_name: str) -> Optional[str]:
        """获取API Key"""
        key_mapping = {
            'deepseek': 'deepseek_api_key',
            'kimi': 'kimi_api_key',
            'qwen': 'qwen_api_key'
        }
        
        key_name = key_mapping.get(model_name)
        if key_name:
            return self.config.get(key_name)
        return None
    
    def call(self, request: AIRequest) -> AIResponse:
        """
        统一调用接口
        
        Args:
            request: AI请求
            
        Returns:
            AI响应
        """
        api_key = self._get_api_key(request.model_name)
        
        if not api_key:
            return AIResponse(
                content="",
                reasoning="",
                model=request.model_name,
                success=False,
                error_message=f"未找到 {request.model_name} 的API Key"
            )
        
        try:
            content, reasoning = call_ai_model(
                model_name=request.model_name,
                api_key=api_key,
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                specific_model=request.specific_model
            )
            
            # 检查是否有错误
            if content.startswith("Error:"):
                return AIResponse(
                    content="",
                    reasoning="",
                    model=request.model_name,
                    success=False,
                    error_message=content
                )
            
            return AIResponse(
                content=content,
                reasoning=reasoning,
                model=request.model_name,
                success=True
            )
            
        except Exception as e:
            logger.error(f"AI调用失败: {e}")
            return AIResponse(
                content="",
                reasoning="",
                model=request.model_name,
                success=False,
                error_message=str(e)
            )
    
    # 便捷方法
    def deepseek(self, prompt: str, system: str = "", model: str = "deepseek-chat") -> AIResponse:
        """调用DeepSeek"""
        return self.call(AIRequest(
            model_name="deepseek",
            user_prompt=prompt,
            system_prompt=system,
            specific_model=model
        ))
    
    def kimi(self, prompt: str, system: str = "", model: str = "kimi-k2.5") -> AIResponse:
        """调用Kimi"""
        return self.call(AIRequest(
            model_name="kimi",
            user_prompt=prompt,
            system_prompt=system,
            specific_model=model
        ))


class StrategyGenerator:
    """
    策略生成器
    
    统一的策略生成接口
    """
    
    def __init__(self):
        self.ai = UnifiedAIInterface()
    
    def generate_strategy(self, symbol: str, context: Dict) -> Dict:
        """
        生成交易策略
        
        Args:
            symbol: 标的代码
            context: 上下文信息(行情、持仓等)
            
        Returns:
            策略结果
        """
        # 构建提示词
        prompt = self._build_strategy_prompt(symbol, context)
        
        # 调用DeepSeek生成策略
        response = self.ai.deepseek(
            prompt=prompt,
            system="你是一个专业的量化交易策略师。",
            model="deepseek-reasoner"
        )
        
        if not response.success:
            return {
                'success': False,
                'error': response.error_message,
                'strategy': None
            }
        
        # 解析策略
        strategy = self._parse_strategy(response.content)
        
        return {
            'success': True,
            'strategy': strategy,
            'reasoning': response.reasoning
        }
    
    def _build_strategy_prompt(self, symbol: str, context: Dict) -> str:
        """构建策略提示词"""
        return f"""请为 {symbol} 制定交易策略。

上下文信息:
- 当前价格: {context.get('price', 'N/A')}
- 持仓情况: {context.get('position', '无持仓')}
- 近期走势: {context.get('trend', 'N/A')}

请输出JSON格式:
{{
    "action": "buy/sell/hold",
    "confidence": 0.85,
    "entry_price": 10.5,
    "stop_loss": 9.8,
    "take_profit": 12.0,
    "reasoning": "策略逻辑"
}}"""
    
    def _parse_strategy(self, content: str) -> Optional[Dict]:
        """解析策略"""
        try:
            # 提取JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"解析策略失败: {e}")
            return None


class RiskAuditor:
    """
    风险审计器
    
    红军审计接口
    """
    
    def __init__(self):
        self.ai = UnifiedAIInterface()
    
    def audit_strategy(self, strategy: Dict, context: Dict) -> Dict:
        """
        审计策略风险
        
        Args:
            strategy: 策略内容
            context: 上下文
            
        Returns:
            审计结果
        """
        prompt = f"""请审计以下交易策略的风险。

策略:
{json.dumps(strategy, ensure_ascii=False, indent=2)}

上下文:
{json.dumps(context, ensure_ascii=False, indent=2)}

请输出JSON格式:
{{
    "risk_score": 5.5,
    "risk_level": "medium",
    "critical_flaws": ["缺陷1"],
    "concerns": ["关注点1"],
    "recommendation": "建议"
}}"""
        
        response = self.ai.deepseek(
            prompt=prompt,
            system="你是一个严格的风险控制官。",
            model="deepseek-reasoner"
        )
        
        if not response.success:
            return {
                'success': False,
                'error': response.error_message,
                'risk_score': 10.0,  # 出错时默认高风险
                'audit': None
            }
        
        audit = self._parse_audit(response.content)
        
        return {
            'success': True,
            'risk_score': audit.get('risk_score', 5.0) if audit else 5.0,
            'audit': audit
        }
    
    def _parse_audit(self, content: str) -> Optional[Dict]:
        """解析审计结果"""
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"解析审计结果失败: {e}")
            return None


def quick_analyze(symbol: str, content: str) -> Dict:
    """
    快速分析
    
    命令行快速调用示例
    """
    ai = UnifiedAIInterface()
    
    prompt = f"分析 {symbol}: {content}"
    
    response = ai.deepseek(
        prompt=prompt,
        system="你是一个金融分析师。"
    )
    
    return {
        'symbol': symbol,
        'analysis': response.content if response.success else response.error_message,
        'success': response.success
    }


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 测试统一AI接口")
    print("=" * 50)
    
    ai = UnifiedAIInterface()
    
    # 测试DeepSeek
    response = ai.deepseek(
        prompt="你好，请简单介绍自己。",
        system="你是一个助手。"
    )
    
    if response.success:
        print(f"✅ DeepSeek调用成功")
        print(f"内容: {response.content[:100]}...")
    else:
        print(f"❌ DeepSeek调用失败: {response.error_message}")
