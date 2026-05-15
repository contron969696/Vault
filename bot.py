import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from utils.logger import setup_logger
from utils.database import db

load_dotenv()
logger = setup_logger()

# ── Bot Configuration ──────────────────────────────────────────────────────────
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

COGS = [
    "cogs.economy",
    "cogs.admin",
    "cogs.shop",
    "cogs.casino",
    "cogs.stocks",
    "cogs.help",  # must be last
]

# ── Bot Class ──────────────────────────────────────────────────────────────────
class Vault(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",  # Change or remove if using slash commands only
            intents=INTENTS,
            help_command=None,  # We'll build a custom one later
            case_insensitive=True,
        )

    async def setup_hook(self):
        """Runs once on startup — loads all cogs."""
        await db.setup()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Sync slash commands to Discord
        await self.tree.sync()
        logger.info("Slash commands synced.")

    async def on_ready(self):
        logger.info(f"Vault is online as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the economy 💰"
            )
        )

    async def on_command_error(self, ctx, error):
        """Global error handler."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Invalid argument provided.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Cooldown! Try again in `{error.retry_after:.1f}s`")
        else:
            logger.error(f"Unhandled error in {ctx.command}: {error}")


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not found in .env file.")

    bot = Vault()
    bot.run(token, log_handler=None)  # log_handler=None uses our custom logger