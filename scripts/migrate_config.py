from utils.config import load_config, save_config

print("Migrating config to include prompts...")
config = load_config()

# load_config already merges defaults into the returned dict
# so simply saving it back will write the defaults (including 'prompts') to disk
save_config(config)

print("Migration complete. 'prompts' section added to user_config.json")
