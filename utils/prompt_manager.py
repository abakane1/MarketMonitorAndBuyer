import os
import json
import random
from pathlib import Path
from typing import Tuple, Dict, List, Any
from utils.prompt_loader import load_prompt_file, PROMPTS_DIR, PROMPT_MAPPINGS
import logging

logger = logging.getLogger(__name__)

class PromptManager:
    """提示词版本管理与 A/B 测试自动优化系统"""
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.ab_test_config_path = "user_data/ab_test_config.json"
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.ab_test_config_path):
            with open(self.ab_test_config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}
            
    def _save_config(self):
        os.makedirs(os.path.dirname(self.ab_test_config_path), exist_ok=True)
        with open(self.ab_test_config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def get_prompt_with_version(self, key: str, enable_ab_test: bool = True) -> Tuple[str, str]:
        """
        获取提示词内容及其版本号
        如果该提示词目录下有多个版本 (如 xxx.md, xxx_v2.md)，则根据权重自动选取或均匀A/B测试。
        
        返回: (提示词内容, 版本标识如 'v1')
        """
        if key not in PROMPT_MAPPINGS:
            logger.warning(f"未知提示词键值: {key}")
            return "", "unknown"
            
        subdir, base_filename = PROMPT_MAPPINGS[key]
        base_name = base_filename.replace('.md', '')
        
        dir_path = PROMPTS_DIR / subdir
        versions = []
        if dir_path.exists():
            for f in dir_path.glob(f"{base_name}*.md"):
                version_suffix = f.stem.replace(base_name, '')
                version = "v1" if not version_suffix else version_suffix.lstrip('_')
                versions.append((version, f))
                
        if not versions:
            logger.error(f"找不到提示词文件: {dir_path}/{base_filename}")
            return "", "v1"
            
        selected_version = "v1"
        # 默认匹配原始文件
        selected_file = next((f for v, f in versions if v == "v1"), versions[0][1])
        
        if enable_ab_test and len(versions) > 1:
            weights = self.config.get(key, {}).get("weights", {})
            choices = [v[0] for v in versions]
            
            if weights:
                # 按照动态权重进行随机（比如有些版本胜率高，被命中的概率就大）
                probs = [weights.get(v, 1.0) for v in choices]
                total = sum(probs)
                if total > 0:
                    probs = [p/total for p in probs]
                    selected_version = random.choices(choices, weights=probs, k=1)[0]
                    selected_file = next(f for v, f in versions if v == selected_version)
            else:
                # 均匀分配流量 (A/B Test)
                selected_version, selected_file = random.choice(versions)
                
        content = load_prompt_file(selected_file)
        return content, selected_version

    def record_feedback(self, key: str, version: str, success: bool):
        """
        基于策略的后续回测或最终人工放行结果，更新某一版本提示词的成功权重。
        以此实现 AI 的提示词闭环自我进化。
        """
        if key not in self.config:
            self.config[key] = {"weights": {}, "stats": {}}
            
        stats = self.config[key]["stats"].setdefault(version, {"success": 0, "fail": 0})
        
        if success:
            stats["success"] += 1
        else:
            stats["fail"] += 1
            
        # 简单的自动优化公式：根据累计胜率调整下一次被选中的概率权重
        total = stats["success"] + stats["fail"]
        if total >= 3: # 积累足够样本数才开始倾斜
            win_rate = stats["success"] / total
            # 基础权重 1.0，根据胜率动态浮动 (胜率 > 50% 加大权重，反之减少)
            new_weight = max(0.1, 1.0 + (win_rate - 0.5) * 2)
            self.config[key]["weights"][version] = round(float(new_weight), 2)
            
        self._save_config()

    def get_all(self, enable_ab_test: bool = True) -> Tuple[Dict[str, str], Dict[str, str]]:
        """批量获取所有提示词及其被选中的版本号"""
        prompts = {}
        versions = {}
        for key in PROMPT_MAPPINGS:
            content, version = self.get_prompt_with_version(key, enable_ab_test)
            prompts[key] = content
            versions[key] = version
        return prompts, versions

# 全局单例
prompt_manager = PromptManager()

def get_all_prompts(enable_ab_test: bool = True) -> Dict[str, str]:
    """向后兼容原始的 load_all_prompts，自动忽略版本信息"""
    prompts, _ = prompt_manager.get_all(enable_ab_test)
    return prompts

