import discord
from collections import defaultdict

GREEN  = 0x2ECC71
RED    = 0xE74C3C
GOLD   = 0xF1C40F
BLUE   = 0x3498DB
PURPLE = 0x9B59B6
GREY   = 0x95A5A6

CURRENCY = "💰"

_registry: dict[str, list[tuple[str, str]]] = defaultdict(list)

CATEGORY_EMOJIS = {
    "Economy":  "💰",
    "Earning":  "⚒️",
    "Skills":   "🎒",
    "Social":   "👥",
    "Shop":     "🛒",
    "Casino":   "🎰",
    "Admin":    "🔧",
}

def register_command(category: str, description: str):
    def decorator(func):
        name = func.callback.__name__ if hasattr(func, "callback") else func.__name__
        _registry[category].append((name, description))
        return func
    return decorator

def get_registry():
    return dict(_registry)

def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=GREEN)

def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=RED)

def info_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=BLUE)

def economy_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"{CURRENCY} {title}", description=description, color=GOLD)

def fmt_currency(amount: int) -> str:
    return f"{CURRENCY} {amount:,}"

def prestige_multiplier(prestige: int) -> float:
    """Each prestige level adds 5% to all earnings."""
    return 1.0 + (prestige * 0.05)

def apply_prestige(amount: int, prestige: int) -> int:
    return int(amount * prestige_multiplier(prestige))