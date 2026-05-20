import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.database import db
from utils.helpers import (
    economy_embed, error_embed, success_embed, info_embed,
    fmt_currency, register_command, apply_prestige
)
from utils.levels import grant_xp

PROPERTIES = [
    ("Lemonade Stand",  "A humble street-side stand.",           50_000,     7,    120),
    ("Food Truck",      "A mobile kitchen on wheels.",           200_000,    22,   240),
    ("Corner Store",    "A neighbourhood convenience store.",    750_000,    83,   360),
    ("Restaurant",      "A full-service dining establishment.",  2_500_000,  174,  480),
    ("Shopping Mall",   "A multi-store retail complex.",         8_000_000,  444,  720),
    ("Corporation",     "A sprawling business empire.",          25_000_000, 694,  1440),
]

PROPERTY_MAP    = {p[0].lower(): p for p in PROPERTIES}
SELL_PERCENTAGE = 0.50


def calc_pending(last_collected_str: str, payout_per_min: int, cap_minutes: int) -> tuple[int, float]:
    if not last_collected_str:
        return 0, 0
    last        = datetime.fromisoformat(last_collected_str)
    elapsed_min = (datetime.utcnow() - last).total_seconds() / 60
    clamped_min = min(elapsed_min, cap_minutes)
    return int(clamped_min * payout_per_min), clamped_min


def fmt_time(minutes: float) -> str:
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes}m"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if m else f"{h}h"


async def maybe_levelup(interaction, leveled_up, new_level):
    if not leveled_up:
        return
    from utils.levels import get_title, TITLES
    title     = get_title(new_level)
    title_str = f'\nYou earned the title **"{title}"**! 🏆' if new_level in TITLES else ""
    await interaction.followup.send(
        embed=discord.Embed(
            title=f"⬆️ Level Up! You're now Level {new_level}!",
            description=f"Keep going to unlock more content.{title_str}",
            color=0xF1C40F
        ),
        ephemeral=False
    )


class Properties(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="properties", description="Browse all available properties to buy.")
    @register_command("Economy", "Browse all properties, their costs, and passive income rates.")
    async def properties(self, interaction: discord.Interaction):
        owned = {r["name"] for r in await db.get_owned_properties(interaction.user.id)}
        lines = []
        for name, desc, cost, ppm, cap in PROPERTIES:
            marker  = "✅ " if name in owned else ""
            sell    = int(cost * SELL_PERCENTAGE)
            cap_str = fmt_time(cap)
            lines.append(
                f"{marker}**{name}** — {fmt_currency(cost)} · Sell: {fmt_currency(sell)}\n"
                f"*{desc}*\n"
                f"Income: {fmt_currency(ppm)}/min · Cap: {cap_str} · Max/collect: {fmt_currency(ppm * cap)}"
            )
        embed = economy_embed(
            "🏢 Properties",
            "\n\n".join(lines) +
            "\n\n`/buy-property <name>` to purchase · `/collect` to collect income"
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="buy-property", description="Buy a property for passive income.")
    @app_commands.describe(property_name="Name of the property to buy")
    @register_command("Economy", "Buy a property that generates passive income over time.")
    async def buy_property(self, interaction: discord.Interaction, property_name: str):
        matched = PROPERTY_MAP.get(property_name.lower())
        if not matched:
            return await interaction.response.send_message(
                embed=error_embed("Not Found", f"No property called **{property_name}**.\nUse `/properties` to browse."),
                ephemeral=False
            )
        name, desc, cost, ppm, cap = matched
        user = await db.get_user(interaction.user.id)

        if await db.owns_property(interaction.user.id, name):
            return await interaction.response.send_message(
                embed=error_embed("Already Owned", f"You already own a **{name}**."), ephemeral=False
            )

        if user["balance"] < cost:
            short = cost - user["balance"]
            msg   = f"**{name}** costs {fmt_currency(cost)} from your wallet.\nYou need {fmt_currency(short)} more."
            if user["bank"] >= short:
                msg += "\n\nYou have enough in your bank — use `/withdraw` first."
            return await interaction.response.send_message(
                embed=error_embed("Insufficient Wallet Funds", msg), ephemeral=False
            )

        await db.update_balance(interaction.user.id, -cost)
        await db.buy_property(interaction.user.id, name)
        await db.log_transaction(interaction.user.id, -cost, f"buy_property_{name}")
        await interaction.response.send_message(embed=success_embed(
            "Property Purchased!",
            f"You bought **{name}** for {fmt_currency(cost)}.\n"
            f"It earns {fmt_currency(ppm)}/min, capped at {fmt_time(cap)}.\n"
            f"Use `/collect` to collect your income."
        ))

    @app_commands.command(name="collect", description="Collect passive income from all your properties.")
    @register_command("Economy", "Collect accumulated income from all owned properties.")
    async def collect(self, interaction: discord.Interaction):
        owned = await db.get_owned_properties(interaction.user.id)
        if not owned:
            return await interaction.response.send_message(
                embed=info_embed("No Properties", "You don't own any properties yet.\nUse `/properties` to browse."),
                ephemeral=False
            )
        user     = await db.get_user(interaction.user.id)
        prestige = user.get("prestige") or 0
        total    = 0
        lines    = []
        now      = datetime.utcnow().isoformat()

        for row in owned:
            name = row["name"]
            prop = PROPERTY_MAP.get(name.lower())
            if not prop:
                continue
            _, _, _, ppm, cap = prop
            pending, elapsed  = calc_pending(row["last_collected"], ppm, cap)
            if pending <= 0:
                lines.append(f"**{name}** — nothing to collect yet.")
                continue
            payout = apply_prestige(pending, prestige)
            total += payout
            await db.update_property_collected(interaction.user.id, name, now)
            lines.append(f"**{name}** — collected {fmt_currency(payout)} ({fmt_time(elapsed)} of income)")

        if total > 0:
            await db.update_balance(interaction.user.id, total)
            await db.log_transaction(interaction.user.id, total, "property_collect")
            await db.grow_bank_limit(interaction.user.id, total)
            xp = 20 + (total // 500)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            lines.append(f"\n+{xp} XP")

        embed = success_embed(f"Collected {fmt_currency(total)}", "\n".join(lines)) if total > 0 else \
                info_embed("Nothing to Collect", "\n".join(lines) + "\n\nCome back later!")
        await interaction.response.send_message(embed=embed)

        if total > 0:
            await maybe_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="my-properties", description="View your owned properties and pending income.")
    @register_command("Economy", "View all owned properties with pending income and time until cap.")
    async def my_properties(self, interaction: discord.Interaction):
        owned = await db.get_owned_properties(interaction.user.id)
        if not owned:
            return await interaction.response.send_message(
                embed=info_embed("No Properties", "You don't own any properties yet.\nUse `/properties` to browse."),
                ephemeral=False
            )
        user          = await db.get_user(interaction.user.id)
        prestige      = user.get("prestige") or 0
        total_pending = 0
        lines         = []

        for row in owned:
            name = row["name"]
            prop = PROPERTY_MAP.get(name.lower())
            if not prop:
                continue
            _, _, cost, ppm, cap = prop
            pending, elapsed     = calc_pending(row["last_collected"], ppm, cap)
            payout               = apply_prestige(pending, prestige)
            total_pending       += payout
            remaining_min        = max(0, cap - elapsed)
            cap_str = "⚠️ **Capped** — collect now!" if remaining_min <= 0 else f"Caps in {fmt_time(remaining_min)}"
            lines.append(
                f"**{name}**\n"
                f" Pending: {fmt_currency(payout)} · {cap_str}\n"
                f" Sell value: {fmt_currency(int(cost * SELL_PERCENTAGE))}"
            )

        embed = economy_embed(
            "🏢 My Properties",
            "\n\n".join(lines) +
            f"\n\n**Total pending: {fmt_currency(total_pending)}**\n"
            f"Use `/collect` to collect all at once."
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="sell-property", description="Sell a property for 50% of its purchase price.")
    @app_commands.describe(property_name="Name of the property to sell")
    @register_command("Economy", "Sell a property back for 50% of its original cost.")
    async def sell_property(self, interaction: discord.Interaction, property_name: str):
        matched = PROPERTY_MAP.get(property_name.lower())
        if not matched:
            return await interaction.response.send_message(
                embed=error_embed("Not Found", f"No property called **{property_name}**.\nUse `/my-properties`."),
                ephemeral=False
            )
        name, _, cost, ppm, cap = matched
        if not await db.owns_property(interaction.user.id, name):
            return await interaction.response.send_message(
                embed=error_embed("Not Owned", f"You don't own a **{name}**."), ephemeral=False
            )
        user          = await db.get_user(interaction.user.id)
        prestige      = user.get("prestige") or 0
        row           = await db.get_owned_property(interaction.user.id, name)
        pending, _    = calc_pending(row["last_collected"], ppm, cap)
        final_pending = apply_prestige(pending, prestige)
        sell_price    = int(cost * SELL_PERCENTAGE)
        total_received= sell_price + final_pending

        await db.sell_property(interaction.user.id, name)
        await db.update_balance(interaction.user.id, total_received)
        await db.log_transaction(interaction.user.id, sell_price, f"sell_property_{name}")
        if final_pending > 0:
            await db.log_transaction(interaction.user.id, final_pending, f"property_collect_on_sell_{name}")

        desc = f"Sold **{name}** for {fmt_currency(sell_price)}."
        if final_pending > 0:
            desc += f"\nAlso collected {fmt_currency(final_pending)} in pending income."
        desc += f"\n**Total received: {fmt_currency(total_received)}**"
        await interaction.response.send_message(embed=success_embed("Property Sold!", desc))


async def setup(bot):
    await bot.add_cog(Properties(bot))