import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from utils.database import db
from utils.helpers import (
    economy_embed, error_embed, success_embed, info_embed,
    fmt_currency, register_command
)
from utils.levels import grant_xp

STOCKS = {
    "AAPL":  "Apricot Inc.",
    "MSFT":  "Microsoar Corp.",
    "NVDA":  "Nvidium Technologies",
    "AMZN":  "Amazonia Group",
    "GOOGL": "Alphabeta Inc.",
    "META":  "Metaverse Co.",
    "BRK-B": "Birkwood Holdings",
    "TSLA":  "Teslon Motors",
    "AVGO":  "Broadwave Systems",
    "JPM":   "JPMorgue & Co.",
}


def price_arrow(price, prev):
    if prev <= 0 or price == prev: return "➡️"
    return "📈" if price > prev else "📉"

def pct_change(price, prev):
    if prev <= 0: return ""
    pct  = ((price - prev) / prev) * 100
    sign = "+" if pct >= 0 else ""
    return f" ({sign}{pct:.2f}%)"

def fmt_price(price):
    return f"💵 {price:,.2f}"


async def fetch_prices_async():
    import yfinance as yf
    prices = {}
    for ticker in STOCKS:
        try:
            t              = yf.Ticker(ticker)
            info           = t.fast_info
            prices[ticker] = round(float(info["lastPrice"]), 2)
        except Exception:
            pass
    return prices


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


class Stocks(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.price_update_loop.start()

    def cog_unload(self):
        self.price_update_loop.cancel()

    @tasks.loop(hours=1)
    async def price_update_loop(self):
        await self._update_prices()

    @price_update_loop.before_loop
    async def before_price_loop(self):
        await self.bot.wait_until_ready()
        await self._update_prices()

    async def _update_prices(self):
        try:
            loop   = asyncio.get_event_loop()
            prices = await loop.run_in_executor(None, lambda: asyncio.run(fetch_prices_async()))
            for ticker, price in prices.items():
                await db.update_stock_price(ticker, price)
        except Exception as e:
            import logging
            logging.getLogger("vault").error(f"Stock price update failed: {e}")

    @app_commands.command(name="stocks", description="View all available stocks and current prices.")
    @register_command("Economy", "Browse all 10 stocks with live prices and % change.")
    async def stocks(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await db.get_all_stocks()
        if not rows or all(r["price"] == 0 for r in rows):
            return await interaction.followup.send(
                embed=error_embed("Prices Unavailable", "Stock prices are still loading. Try again in a moment."),
                ephemeral=False
            )
        lines = []
        for r in rows:
            arrow  = price_arrow(r["price"], r["prev_price"])
            change = pct_change(r["price"], r["prev_price"])
            lines.append(f"{arrow} **{r['fake_name']}** (`{r['ticker']}`)\n  {fmt_price(r['price'])}{change}")
        updated = rows[0]["last_updated"] or "never"
        embed   = info_embed(
            "📈 Vault Stock Exchange",
            "\n\n".join(lines) +
            f"\n\n*Prices update hourly · Last updated: {updated} UTC*\n"
            f"Use `/buy-stock <ticker> <shares>` to invest."
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buy-stock", description="Buy shares of a stock.")
    @app_commands.describe(ticker="Stock ticker (e.g. AAPL)", shares="Number of whole shares to buy")
    @register_command("Economy", "Buy shares of a stock using coins from your wallet.")
    async def buy_stock(self, interaction: discord.Interaction, ticker: str, shares: int):
        ticker = ticker.upper()
        if ticker not in STOCKS:
            return await interaction.response.send_message(
                embed=error_embed("Unknown Stock", f"`{ticker}` is not valid. Use `/stocks` to browse."),
                ephemeral=False
            )
        if shares <= 0:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Shares must be at least 1."), ephemeral=False
            )
        stock = await db.get_stock(ticker)
        if not stock or stock["price"] == 0:
            return await interaction.response.send_message(
                embed=error_embed("Price Unavailable", "This stock's price hasn't loaded yet. Try again shortly."),
                ephemeral=False
            )
        user       = await db.get_user(interaction.user.id)
        total_cost = int(shares * stock["price"])
        if user["balance"] < total_cost:
            short = total_cost - user["balance"]
            msg   = f"**{STOCKS[ticker]}** — {shares} share{'s' if shares > 1 else ''} costs {fmt_currency(total_cost)}.\nYou need {fmt_currency(short)} more."
            if user["bank"] >= short:
                msg += "\n\nYou have enough in your bank — use `/withdraw` first."
            return await interaction.response.send_message(
                embed=error_embed("Insufficient Funds", msg), ephemeral=False
            )
        success = await db.buy_stock(interaction.user.id, ticker, shares, stock["price"])
        if not success:
            return await interaction.response.send_message(
                embed=error_embed("Purchase Failed", "Something went wrong. Try again."), ephemeral=False
            )
        xp = 10
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(embed=success_embed(
            "Stock Purchased!",
            f"Bought **{shares}x {STOCKS[ticker]}** (`{ticker}`)\n"
            f"Price per share: {fmt_price(stock['price'])}\n"
            f"Total cost: {fmt_currency(total_cost)}\n"
            f"+{xp} XP"
        ))
        await maybe_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="sell-stock", description="Sell shares of a stock.")
    @app_commands.describe(ticker="Stock ticker (e.g. AAPL)", shares="Number of shares to sell")
    @register_command("Economy", "Sell shares and receive coins directly to your wallet.")
    async def sell_stock(self, interaction: discord.Interaction, ticker: str, shares: int):
        ticker = ticker.upper()
        if ticker not in STOCKS:
            return await interaction.response.send_message(
                embed=error_embed("Unknown Stock", f"`{ticker}` is not valid. Use `/stocks` to browse."),
                ephemeral=False
            )
        if shares <= 0:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Shares must be at least 1."), ephemeral=False
            )
        stock = await db.get_stock(ticker)
        if not stock or stock["price"] == 0:
            return await interaction.response.send_message(
                embed=error_embed("Price Unavailable", "Price hasn't loaded yet."), ephemeral=False
            )
        portfolio = await db.get_portfolio(interaction.user.id)
        holding   = next((h for h in portfolio if h["ticker"] == ticker), None)
        avg_cost  = holding["avg_cost"] if holding else stock["price"]

        success, proceeds = await db.sell_stock(interaction.user.id, ticker, shares, stock["price"])
        if not success:
            return await interaction.response.send_message(
                embed=error_embed("Can't Sell", f"You don't have {shares} shares of `{ticker}`.\nCheck `/portfolio`."),
                ephemeral=False
            )
        profit     = proceeds - int(shares * avg_cost)
        sold_profit= profit > 0
        xp         = 30 if sold_profit else 10
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        pl_str  = f"+{fmt_currency(profit)}" if profit >= 0 else fmt_currency(profit)
        pl_emoji= "📈" if profit >= 0 else "📉"
        await interaction.response.send_message(embed=success_embed(
            "Stock Sold!",
            f"Sold **{shares}x {STOCKS[ticker]}** (`{ticker}`)\n"
            f"Price per share: {fmt_price(stock['price'])}\n"
            f"Proceeds: {fmt_currency(proceeds)} → added to wallet\n"
            f"P/L: {pl_emoji} {pl_str}\n"
            f"+{xp} XP{'  *(profit bonus!)*' if sold_profit else ''}"
        ))
        await maybe_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="portfolio", description="View your stock holdings.")
    @register_command("Economy", "View all your stock holdings with current value and profit/loss.")
    async def portfolio(self, interaction: discord.Interaction):
        holdings = await db.get_portfolio(interaction.user.id)
        if not holdings:
            return await interaction.response.send_message(
                embed=info_embed("📊 Your Portfolio", "You don't own any stocks yet.\nUse `/stocks` to browse and `/buy-stock` to invest."),
                ephemeral=False
            )
        lines          = []
        total_value    = 0
        total_invested = 0
        for h in holdings:
            current_val = int(h["shares"] * h["current_price"])
            invested    = int(h["shares"] * h["avg_cost"])
            pl          = current_val - invested
            pl_str      = f"+{fmt_currency(pl)}" if pl >= 0 else fmt_currency(pl)
            pl_emoji    = "📈" if pl >= 0 else "📉"
            total_value    += current_val
            total_invested += invested
            lines.append(
                f"**{h['fake_name']}** (`{h['ticker']}`)\n"
                f"  {h['shares']} shares · {fmt_price(h['current_price'])}/share\n"
                f"  Value: {fmt_currency(current_val)} · P/L: {pl_emoji} {pl_str}"
            )
        total_pl     = total_value - total_invested
        total_pl_str = f"+{fmt_currency(total_pl)}" if total_pl >= 0 else fmt_currency(total_pl)
        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"**Total Value:** {fmt_currency(total_value)}\n"
            f"**Total P/L:** {'📈' if total_pl >= 0 else '📉'} {total_pl_str}"
        )
        await interaction.response.send_message(
            embed=info_embed("📊 Your Portfolio", "\n\n".join(lines)), ephemeral=False
        )


async def setup(bot):
    await bot.add_cog(Stocks(bot))