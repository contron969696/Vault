import discord
from discord.ext import commands
from discord import app_commands

from utils.helpers import get_registry, CATEGORY_EMOJIS, register_command


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="See all available commands.")
    @register_command("Economy", "See all available Vault commands organized by category.")
    async def help(self, interaction: discord.Interaction):
        registry = get_registry()
        embed = discord.Embed(
            title="📖 Vault — Command List",
            description="Use `/command` to run any of these.",
            color=0x5865F2
        )
        order = ["Economy", "Earning", "Skills", "Shop", "Social", "Casino"]
        sorted_cats = sorted(registry.keys(), key=lambda c: order.index(c) if c in order else 99)
        for cat in sorted_cats:
            cmds  = registry[cat]
            emoji = CATEGORY_EMOJIS.get(cat, "•")
            lines = [f"`/{name}` — {desc}" for name, desc in sorted(cmds)]
            embed.add_field(name=f"{emoji} {cat}", value="\n".join(lines), inline=False)
        embed.set_footer(text="Vault Economy Bot")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))