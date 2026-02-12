# -*- coding: utf-8 -*-
"""
Prompt Loader Module

Loads prompts from Markdown files in the prompts/ directory.
Replaces the old encrypted JSON approach with human-readable, version-controlled prompts.

Usage:
    from utils.prompt_loader import load_prompt, load_all_prompts
    
    # Load single prompt
    system_prompt = load_prompt('system', 'proposer_system')
    
    # Load all prompts as config dict
    prompts_config = load_all_prompts()
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Mapping from config keys to file paths
# This allows backward compatibility with old code using different key names
PROMPT_MAPPINGS = {
    # System prompts
    'proposer_system': ('system', 'proposer_system.md'),
    'reviewer_system': ('system', 'reviewer_system.md'),
    'blue_quant_sys': ('agents', 'blue_quant_sys.md'),
    'quant_agent_system': ('agents', 'blue_quant_sys.md'),  # alias
    'blue_intel_sys': ('agents', 'blue_intel_sys.md'),
    'intel_agent_system': ('agents', 'blue_intel_sys.md'),  # alias
    'red_quant_auditor_system': ('agents', 'red_quant_sys.md'),
    'red_intel_auditor_system': ('agents', 'red_intel_sys.md'),
    
    # User prompt templates
    'proposer_base': ('user', 'proposer_base.md'),
    'proposer_premarket_suffix': ('user', 'proposer_premarket_suffix.md'),
    'proposer_intraday_suffix': ('user', 'proposer_intraday_suffix.md'),
    'proposer_noon_suffix': ('user', 'proposer_noon_suffix.md'),
    'proposer_simple_suffix': ('user', 'proposer_simple_suffix.md'),
    
    # Audit prompts
    'reviewer_audit': ('audit', 'reviewer_audit.md'),
    'reviewer_final_audit': ('audit', 'reviewer_final_audit.md'),
    'refinement_instruction': ('audit', 'refinement_instruction.md'),
    
    # Final decision
    'proposer_final_decision': ('final', 'proposer_final_decision.md'),
    
    # Legacy mappings for backward compatibility
    'deepseek_research_suffix': ('user', 'proposer_premarket_suffix.md'),
    'qwen_system': ('system', 'reviewer_system.md'),
    'qwen_audit': ('audit', 'reviewer_audit.md'),
    'deepseek_final_decision': ('final', 'proposer_final_decision.md'),
}


def load_prompt_file(filepath: Path) -> str:
    """
    Load and parse a markdown prompt file.
    
    Removes the YAML frontmatter (if present) and returns the content.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    
    content = filepath.read_text(encoding='utf-8')
    
    # Remove YAML frontmatter if present
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    
    return content


def load_prompt(subdir: str, filename: str) -> str:
    """
    Load a prompt by subdirectory and filename.
    
    Args:
        subdir: Subdirectory under prompts/ (e.g., 'system', 'user')
        filename: Filename with .md extension
    
    Returns:
        The prompt content as string
    """
    filepath = PROMPTS_DIR / subdir / filename
    return load_prompt_file(filepath)


def load_all_prompts() -> Dict[str, str]:
    """
    Load all prompts and return as a config dictionary.
    
    Returns:
        Dict mapping config keys to prompt content
    """
    prompts = {}
    
    for key, (subdir, filename) in PROMPT_MAPPINGS.items():
        try:
            filepath = PROMPTS_DIR / subdir / filename
            if filepath.exists():
                prompts[key] = load_prompt_file(filepath)
        except Exception as e:
            print(f"Warning: Failed to load prompt '{key}' from {subdir}/{filename}: {e}")
    
    return prompts


def save_prompt(key: str, content: str) -> None:
    """
    Save a prompt back to its file.
    
    Args:
        key: The config key for the prompt
        content: New content to save
    """
    if key not in PROMPT_MAPPINGS:
        raise KeyError(f"Unknown prompt key: {key}")
    
    subdir, filename = PROMPT_MAPPINGS[key]
    filepath = PROMPTS_DIR / subdir / filename
    
    # Preserve YAML frontmatter if it exists
    existing_content = ""
    if filepath.exists():
        existing_content = filepath.read_text(encoding='utf-8')
    
    frontmatter = ""
    if existing_content.startswith('---'):
        parts = existing_content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = f"---{parts[1]}---\n\n"
    
    filepath.write_text(frontmatter + content, encoding='utf-8')


def list_available_prompts() -> Dict[str, tuple]:
    """
    List all available prompts and their file paths.
    
    Returns:
        Dict mapping config keys to (subdir, filename) tuples
    """
    return PROMPT_MAPPINGS.copy()


def reload_prompt_from_file(key: str) -> Optional[str]:
    """
    Force reload a specific prompt from disk.
    
    Args:
        key: The config key to reload
    
    Returns:
        The prompt content, or None if not found
    """
    if key not in PROMPT_MAPPINGS:
        return None
    
    subdir, filename = PROMPT_MAPPINGS[key]
    filepath = PROMPTS_DIR / subdir / filename
    
    if filepath.exists():
        return load_prompt_file(filepath)
    return None
