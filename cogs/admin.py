import logging
from pathlib import Path
import discord
from discord.ext import commands
from configManager import ConfigManager
from utils import guild_state
from utils.library import load_library, save_library
logger = logging.getLogger("newBaldy.admin")


class AdminCog(commands.Cog, name="Admin"):
    def __init__(
        self,
        bot: commands.Bot,
        config_manager: ConfigManager,
        download_folder_path: Path,
        library_path: Path,
    ):
        self.bot = bot
        self.config_manager = config_manager
        self.download_folder_path = download_folder_path
        self.library_path = library_path

    @commands.command(name="shutdown")
    async def shutdown(self, ctx: commands.Context):
        """Shuts down the bot and disconnects from all voice channels. (owner only)"""
        await ctx.send("Shutting down...")
        for gid, vc in list(guild_state.guild_voice_clients.items()):
            try:
                if vc and vc.is_connected():
                    await vc.disconnect()
            except Exception:
                logger.exception("Error disconnecting VC during shutdown for guild %s", gid)
        await self.bot.close()

    @commands.command(name="remove")
    async def remove_song(self, ctx: commands.Context, video_id: str):
        """Removes a song from the library and download folder by video ID. (owner only)"""
        try:
            library = load_library(self.library_path)
            if video_id not in library:
                await ctx.send(f"No song found with ID: `{video_id}`")
                return

            song_title = library[video_id]["title"]
            del library[video_id]
            save_library(library, self.library_path)

            file_path = self.download_folder_path / f"{video_id}.webm"
            if file_path.exists():
                file_path.unlink()
                await ctx.send(f"Removed **{song_title}** from the library and deleted the file.")
            else:
                await ctx.send(
                    f"Removed **{song_title}** from the library, "
                    f"but the file was not found in the downloads folder."
                )

            for gid in guild_state.guild_queues:
                guild_state.guild_queues[gid] = [
                    song for song in guild_state.guild_queues[gid]
                    if song.get("id") != video_id
                ]

        except Exception as e:
            logger.exception("Error removing song %s: %s", video_id, e)
            await ctx.send(f"An error occurred: {e}")

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.author.id != self.config_manager.bot_owner:
            raise commands.NotOwner("You are not the bot owner.")
        return True


async def setup(bot: commands.Bot, config_manager: ConfigManager, download_folder_path: Path, library_path: Path):
    await bot.add_cog(AdminCog(bot, config_manager, download_folder_path, library_path))
