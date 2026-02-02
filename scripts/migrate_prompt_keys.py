#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
migrate_prompt_keys.py

This script migrates prompt keys from the legacy model-specific naming convention
(deepseek_*, qwen_*) to the new role-based naming convention (proposer_*, reviewer_*).
"""

from utils.config import load_config, save_config

KEY_MAPPING = {
    # Proposer keys
    "deepseek_system": "proposer_system",
    "deepseek_base": "proposer_base",
    "deepseek_new_strategy_suffix": "proposer_premarket_suffix",
    "deepseek_intraday_suffix": "proposer_intraday_suffix",
    "deepseek_noon_suffix": "proposer_noon_suffix",
    "deepseek_simple_suffix": "proposer_simple_suffix",
    "deepseek_final_decision": "proposer_final_decision",
    # Reviewer keys
    "qwen_system": "reviewer_system",
    "qwen_audit": "reviewer_audit",
    "qwen_final_audit": "reviewer_final_audit",
}

def migrate_prompts():
    config = load_config()
    prompts = config.get("prompts", {})
    
    if not isinstance(prompts, dict):
        print("Error: prompts is not a dict (might be encrypted). Decryption happens in load_config, check if key is correct.")
        return
    
    migrated = 0
    for old_key, new_key in KEY_MAPPING.items():
        if old_key in prompts:
            prompts[new_key] = prompts.pop(old_key)
            print(f"  Migrated: {old_key} -> {new_key}")
            migrated += 1
        elif new_key in prompts:
            print(f"  Skipped (already migrated): {new_key}")
        else:
            print(f"  Not found: {old_key}")
    
    if migrated > 0:
        config["prompts"] = prompts
        save_config(config)
        print(f"\n✅ Migration complete! {migrated} keys migrated.")
    else:
        print("\n⚠️ No keys to migrate. Already up to date.")

if __name__ == "__main__":
    print("=== Prompt Key Migration Script ===\n")
    migrate_prompts()
