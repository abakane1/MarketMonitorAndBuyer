from utils.config import load_config, save_config

def patch_prompts():
    print("Loading config (auto-decrypting)...")
    config = load_config()
    prompts = config.get("prompts", {})
    
    if not isinstance(prompts, dict):
        print("Prompts not accessible (maybe still encrypted or missing key).")
        return

    updated_count = 0
    
    for key, value in prompts.items():
        original = value
        new_val = value.replace("明天", "下一个交易日")
        new_val = new_val.replace("明日", "下一个交易日")
        new_val = new_val.replace("Tomorrow", "Next Trading Day")
        
        if new_val != original:
            prompts[key] = new_val
            updated_count += 1
            print(f"Patched: {key}")

    if updated_count > 0:
        config["prompts"] = prompts
        print(f"Saving config (auto-encrypting) with {updated_count} updates...")
        save_config(config)
        print("Done.")
    else:
        print("No matches found. Already patched?")

if __name__ == "__main__":
    patch_prompts()
