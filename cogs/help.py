import discord
from discord.ext import commands


class SupremeHelpCommand(commands.HelpCommand):
    def get_command_signature(self, command):
        return f"{self.context.clean_prefix}{command.qualified_name} {command.signature}"

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help", color=discord.Color.blurple())
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)
            if signatures := [self.get_command_signature(c) for c in filtered]:
                cog_name = getattr(cog, "qualified_name", "\u200b")
                embed.add_field(name=cog_name, value="\n".join(signatures), inline=False)
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=self.get_command_signature(command), color=discord.Color.blurple()
        )
        if command.help:
            embed.description = command.help
        if alias := command.aliases:
            embed.add_field(name="Aliases", value=", ".join(alias), inline=False)
        await self.get_destination().send(embed=embed)

    async def _send_help_embed(self, title, description, cmds):
        embed = discord.Embed(title=title, description=description or "No help found...")
        if filtered := await self.filter_commands(cmds):
            for command in filtered:
                embed.add_field(
                    name=self.get_command_signature(command),
                    value=command.help or "No help found...",
                )
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        await self._send_help_embed(
            self.get_command_signature(group), group.help, group.commands
        )

    async def send_cog_help(self, cog):
        title = cog.qualified_name or "No"
        await self._send_help_embed(
            f"{title} Category", cog.description, cog.get_commands()
        )

    async def send_error_message(self, error):
        embed = discord.Embed(title="Error", description=error, color=discord.Color.red())
        await self.get_destination().send(embed=embed)


class HelpCog(commands.Cog, name="Help"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._original_help = bot.help_command
        bot.help_command = SupremeHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
