# -*- coding: utf-8 -*-
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.expert_registry import ExpertRegistry

def test_registry():
    print("Testing ExpertRegistry...")
    
    mock_keys = {
        "deepseek_api_key": "mock_ds_key",
        "qwen_api_key": "mock_qwen_key"
    }
    
    ds = ExpertRegistry.get_expert("DeepSeek", mock_keys)
    assert ds is not None
    assert ds.name == "DeepSeek"
    print("✅ DeepSeek Expert initialized.")
    
    qwen = ExpertRegistry.get_expert("Qwen", mock_keys)
    assert qwen is not None
    assert qwen.name == "Qwen"
    print("✅ Qwen Expert initialized.")
    
    unknown = ExpertRegistry.get_expert("Unknown", mock_keys)
    assert unknown is None
    print("✅ Unknown Expert handled.")
    
    print("All registry tests passed.")

if __name__ == "__main__":
    test_registry()
