import discord
from discord.ext import commands
from discord import app_commands

from utils.database import db
from utils.helpers import success_embed, error_embed, fmt_currency, register_command

OWNER_ID = 123456789012345678  # <-- replace with your Discord user ID

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addmoney", description="[Owner] Add coins to a member's wallet.")
    @app_commands.describe(member="Target member", amount="Amount to add")
    @is_owner()
    async def addmoney(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(embed=error_embed("Invalid", "Amount must be positive."), ephemeral=True)
        await db.update_balance(member.id, amount)
        await db.log_transaction(member.id, amount, "owner_add")
        await interaction.response.send_message(embed=success_embed("Done", f"Gave {fmt_currency(amount)} to {member.mention}."))

    @app_commands.command(name="removemoney", description="[Owner] Remove coins from a member's wallet.")
    @app_commands.describe(member="Target member", amount="Amount to remove")
    @is_owner()
    async def removemoney(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        user = await db.get_user(member.id)
        amt  = min(amount, user["balance"])
        await db.update_balance(member.id, -amt)
        await db.log_transaction(member.id, -amt, "owner_remove")
        await interaction.response.send_message(embed=success_embed("Done", f"Removed {fmt_currency(amt)} from {member.mention}."))

    @app_commands.command(name="resetuser", description="[Owner] Reset a member's economy data.")
    @app_commands.describe(member="Target member")
    @is_owner()
    async def resetuser(self, interaction: discord.Interaction, member: discord.Member):
        await db.reset_user(member.id)
        await interaction.response.send_message(embed=success_embed("Done", f"{member.mention}'s data wiped."))

    async def on_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(embed=error_embed("Access Denied", "Owner only."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))