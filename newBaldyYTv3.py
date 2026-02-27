import asyncio
import logging
from pathlib import Path
import discord
from discord.ext import commands
from configManager import ConfigManager
from utils.library import scan_and_update_library

# Logging
logger = logging.getLogger("newBaldy")
logging.basicConfig(level=logging.INFO)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

# Paths
script_dir = Path(__file__).resolve().parent
config_file_path = script_dir / ".env"
INDEX_FOLDER = script_dir / "index"
INDEX_FOLDER.mkdir(parents=True, exist_ok=True)
library_path = INDEX_FOLDER / "song_library.json"

# Config Validation
config_manager = ConfigManager(str(config_file_path))

download_folder_path = script_dir / config_manager.download_folder
download_folder_path.mkdir(parents=True, exist_ok=True)

# Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info("Logged in as %s. Running library scan...", bot.user.name)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        scan_and_update_library,
        download_folder_path,
        library_path,
        config_manager.download_folder,
    )
    logger.info("Library scan complete. Bot ready.")

async def main():
    async with bot:
        from cogs.help import setup as setup_help
        from cogs.music import setup as setup_music
        from cogs.admin import setup as setup_admin

        await setup_help(bot)
        await setup_music(
            bot,
            config_manager,
            download_folder_path,
            library_path,
            config_manager.download_folder,
        )
        await setup_admin(bot, config_manager, download_folder_path, library_path)

        await bot.start(config_manager.bot_token)

if __name__ == "__main__":
    asyncio.run(main())
