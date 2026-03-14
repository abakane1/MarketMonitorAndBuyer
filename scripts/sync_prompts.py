#!/usr/bin/env python3
"""
同步 user_config.json 中的提示词到 prompts_encrypted.json

用法: python3 sync_prompts.py
"""
import json
import sys
sys.path.insert(0, '.')

from utils.config import load_config, save_config

def main():
    print("正在加载配置...")
    config = load_config()
    
    # 检查是否有提示词
    prompts = config.get("prompts", {})
    if not prompts or not isinstance(prompts, dict):
        print("错误: 未找到有效的提示词配置")
        return 1
    
    # 过滤掉__NOTE__
    valid_prompts = {k: v for k, v in prompts.items() if not k.startswith("__")}
    
    print(f"\n找到 {len(valid_prompts)} 个提示词模板:")
    for key in valid_prompts.keys():
        print(f"  - {key}")
    
    # 保存配置（会自动加密并写入 prompts_encrypted.json）
    print("\n正在同步并加密提示词到 prompts_encrypted.json...")
    config["prompts"] = valid_prompts
    save_config(config)
    
    print("✓ 同步完成！")
    print("\n提示词已加密存储到: prompts_encrypted.json")
    print("源文件: user_config.json 中的 prompts 部分可保留作为备份，或删除以符合安全规范")
    
    return 0

if __name__ == "__main__":
    exit(main())
