"""Run the bot without the GUI, using the settings in config.json (set them up with gui.py)."""
from config import CONFIG_PATH, Config
from discord_bot import VMBot

if __name__ == "__main__":
    config = Config.load()
    if not config.token:
        raise SystemExit(f"No bot token in {CONFIG_PATH}. Run gui.py to set things up.")
    VMBot(config).run(config.token)
