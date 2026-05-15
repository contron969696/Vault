import discord
from discord.ext import commands
from discord import app_commands

from utils.database import db
from utils.helpers import economy_embed, error_embed, success_embed, fmt_currency, register_command


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await db.seed_shop()

    @app_commands.command(name="shop", description="Browse the shop.")
    @register_command("Shop", "Browse all tools and their prices.")
    async def shop(self, interaction: discord.Interaction):
        items = await db.get_shop_items()
        if not items:
            return await interaction.response.send_message(embed=error_embed("Empty", "No items yet."), ephemeral=True)
        lines = [
            f"**{i['name']}** — {fmt_currency(i['price'])} · Sell: {fmt_currency(i['price'] // 2)}\n*{i['description']}*"
            for i in items
        ]
        embed = economy_embed("🛒 Shop", "\n\n".join(lines) + "\n\n`/buy <name>` to purchase · `/sell <name>` to sell for 50%")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="buy", description="Buy a tool from the shop.")
    @app_commands.describe(item_name="Name of the item")
    @register_command("Shop", "Buy a tool from the shop using coins from your wallet.")
    async def buy(self, interaction: discord.Interaction, item_name: str):
        item = await db.get_shop_item_by_name(item_name)
        if not item:
            return await interaction.response.send_message(embed=error_embed("Not Found", f"No item **{item_name}**. Use `/shop`."), ephemeral=True)
        if await db.has_item(interaction.user.id, item["name"]):
            return await interaction.response.send_message(embed=error_embed("Already Owned", f"You already have a **{item['name']}**."), ephemeral=True)
        user = await db.get_user(interaction.user.id)
        if user["balance"] < item["price"]:
            short = item["price"] - user["balance"]
            msg   = f"**{item['name']}** costs {fmt_currency(item['price'])} from your wallet.\nYou need {fmt_currency(short)} more."
            if user["bank"] >= short:
                msg += f"\n\nYou have enough in your bank — use `/withdraw` first."
            return await interaction.response.send_message(embed=error_embed("Insufficient Wallet Funds", msg), ephemeral=True)
        await db.update_balance(interaction.user.id, -item["price"])
        await db.add_item(interaction.user.id, item["item_id"])
        await db.log_transaction(interaction.user.id, -item["price"], f"buy_{item['name']}")
        await interaction.response.send_message(embed=success_embed("Purchased!", f"You bought a **{item['name']}** for {fmt_currency(item['price'])}."))

    @app_commands.command(name="sell", description="Sell a tool for 50% of its value.")
    @app_commands.describe(item_name="Name of the item to sell")
    @register_command("Shop", "Sell a tool back for 50% of its original price.")
    async def sell(self, interaction: discord.Interaction, item_name: str):
        item = await db.get_shop_item_by_name(item_name)
        if not item:
            return await interaction.response.send_message(embed=error_embed("Not Found", f"No item **{item_name}**. Use `/inventory`."), ephemeral=True)
        if not await db.has_item(interaction.user.id, item["name"]):
            return await interaction.response.send_message(embed=error_embed("Not Owned", f"You don't have a **{item['name']}**."), ephemeral=True)
        sell_price = item["price"] // 2
        await db.remove_item(interaction.user.id, item["item_id"])
        await db.update_balance(interaction.user.id, sell_price)
        await db.log_transaction(interaction.user.id, sell_price, f"sell_{item['name']}")
        await interaction.response.send_message(embed=success_embed("Sold!", f"Sold **{item['name']}** for {fmt_currency(sell_price)}."))

    @app_commands.command(name="inventory", description="View your tool inventory.")
    @register_command("Shop", "View all tools you own.")
    async def inventory(self, interaction: discord.Interaction):
        items = await db.get_inventory(interaction.user.id)
        if not items:
            embed = economy_embed("🎒 Inventory", "Empty. Visit `/shop` to buy tools.")
        else:
            lines = [f"**{i['name']}** x{i['quantity']} — sell: {fmt_currency(i['price']//2)}\n*{i['description']}*" for i in items]
            embed = economy_embed("🎒 Inventory", "\n\n".join(lines))
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Shop(bot))