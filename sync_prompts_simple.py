#!/usr/bin/env python3
"""
同步 user_config.json 中的提示词到 prompts_encrypted.json
简化版本，不依赖 streamlit

用法: python3 sync_prompts_simple.py
"""
import json
import os

# 直接导入加密函数
from utils.security import encrypt_dict

CONFIG_FILE = "user_config.json"
PROMPTS_FILE = "prompts_encrypted.json"

def main():
    print("正在加载 user_config.json...")
    
    # 读取 user_config.json
    if not os.path.exists(CONFIG_FILE):
        print(f"错误: {CONFIG_FILE} 文件不存在")
        return 1
    
    with open(CONFIG_FILE, "r", encoding='utf-8') as f:
        config = json.load(f)
    
    # 提取提示词
    prompts = config.get("prompts", {})
    if not prompts or not isinstance(prompts, dict):
        print("错误: 未找到有效的提示词配置")
        return 1
    
    # 过滤掉__NOTE__等元数据
    valid_prompts = {k: v for k, v in prompts.items() if not k.startswith("__")}
    
    print(f"\n找到 {len(valid_prompts)} 个提示词模板:")
    for key in valid_prompts.keys():
        print(f"  ✓ {key}")
    
    # 加密提示词
    print("\n正在加密提示词...")
    encrypted_prompts = encrypt_dict(valid_prompts)
    
    # 写入 prompts_encrypted.json
    print(f"正在写入 {PROMPTS_FILE}...")
    with open(PROMPTS_FILE, "w", encoding='utf-8') as pf:
        json.dump({
            "prompts": encrypted_prompts, 
            "version": "2.5.1"
        }, pf, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 同步完成！")
    print(f"\n提示词已加密存储到: {PROMPTS_FILE}")
    print("下一步:")
    print("  1. [可选] 从 user_config.json 中删除 prompts 部分以符合安全规范")
    print("  2. 重启应用验证提示词能正确从加密文件加载")
    
    return 0

if __name__ == "__main__":
    try:
        exit(main())
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
