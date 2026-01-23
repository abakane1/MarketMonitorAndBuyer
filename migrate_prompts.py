from utils.config import load_config, save_config

def migrate():
    print("Loading config...")
    # This will load plain text prompts (since is_encrypted will return False)
    config = load_config()
    prompts = config.get("prompts")
    
    if isinstance(prompts, dict):
        print("Prompts are currently PLAIN TEXT. Encrypting...")
        # Save config triggers encryption logic
        save_config(config)
        print("Migration complete. Prompts encrypted.")
    else:
        print("Prompts are already ENCRYPTED or invalid.")

if __name__ == "__main__":
    migrate()
