from discord.ext import commands
from configManager import ConfigManager


def is_bot_owner(config_manager: ConfigManager):
    """Check BOT_OWNER in config."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id != config_manager.bot_owner:
            raise commands.NotOwner("You are not the bot owner.")
        return True
    return commands.check(predicate)
