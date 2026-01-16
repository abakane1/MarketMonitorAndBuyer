from utils.config import load_config, save_config, DEFAULT_CONFIG

print("Updating user config with new persona...")
config = load_config()

# Force update the prompts section with the new defaults (which contain the Poker Persona)
# We only update "deepseek_base" to respect if user customized others, 
# but here I think it's safer to just merge specific keys or overwrite prompts if user hasn't customized.
# Given the user REQUESTED this change, I will overwrite `deepseek_base`.

if "prompts" not in config:
    config["prompts"] = {}

new_prompt = DEFAULT_CONFIG["prompts"]["deepseek_base"]
config["prompts"]["deepseek_base"] = new_prompt

save_config(config)
print("Persona updated to Texas Hold'em LAG.")
