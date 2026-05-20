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
        try:
            registry    = get_registry()
            embed       = discord.Embed(
                title="📖 Vault — Command List",
                description="Use `/command` to run any of these.",
                color=0x5865F2
            )
            order       = ["Economy", "Earning", "Skills", "Shop", "Social", "Casino"]
            sorted_cats = sorted(registry.keys(), key=lambda c: order.index(c) if c in order else 99)

            for cat in sorted_cats:
                cmds  = registry[cat]
                emoji = CATEGORY_EMOJIS.get(cat, "•")
                lines = [f"`/{name}` — {desc}" for name, desc in sorted(cmds)]

                # Split into chunks of max 1024 chars to stay within Discord's field limit
                chunks = []
                current = ""
                for line in lines:
                    if len(current) + len(line) + 1 > 1000:
                        chunks.append(current.strip())
                        current = line + "\n"
                    else:
                        current += line + "\n"
                if current:
                    chunks.append(current.strip())

                for i, chunk in enumerate(chunks):
                    field_name = f"{emoji} {cat}" if i == 0 else f"{emoji} {cat} (cont.)"
                    embed.add_field(name=field_name, value=chunk, inline=False)

            embed.set_footer(text="Vault Economy Bot")
            await interaction.response.send_message(embed=embed, ephemeral=False)
        except Exception as e:
            await interaction.response.send_message(f"❌ Help error: `{e}`", ephemeral=False)


async def setup(bot):
    await bot.add_cog(Help(bot))