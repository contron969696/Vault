# utils/levels.py
# Shared XP / level system used across all cogs.

from utils.database import db

# ── XP curve ──────────────────────────────────────────────────────────────────
# Soft cap: fast early, slows significantly after 50, crawl after 75.

MAX_LEVEL = 100

def xp_for_level(level: int) -> int:
    """XP required to reach `level` from `level - 1`."""
    if level <= 10:
        return 500
    elif level <= 25:
        return 2_000
    elif level <= 50:
        return 8_000
    elif level <= 75:
        return 25_000
    else:
        return 75_000

def total_xp_for_level(level: int) -> int:
    """Cumulative XP needed to reach `level` from level 1."""
    return sum(xp_for_level(l) for l in range(2, level + 1))

def level_from_xp(xp: int) -> int:
    """Return current level given total XP."""
    level = 1
    while level < MAX_LEVEL and xp >= total_xp_for_level(level + 1):
        level += 1
    return level

def xp_progress(xp: int) -> tuple[int, int, int]:
    """
    Returns (current_level, xp_into_level, xp_needed_for_next).
    xp_into_level  = XP accumulated since the start of current level.
    xp_needed      = total XP required to complete current level.
    """
    level = level_from_xp(xp)
    if level >= MAX_LEVEL:
        return level, 0, 0
    xp_at_level_start = total_xp_for_level(level)
    xp_into = xp - xp_at_level_start
    xp_needed = xp_for_level(level + 1)
    return level, xp_into, xp_needed

def xp_bar(xp_into: int, xp_needed: int, bar_len: int = 20) -> str:
    """Render a text progress bar."""
    if xp_needed == 0:
        return "█" * bar_len  # max level
    filled = int((xp_into / xp_needed) * bar_len)
    return "█" * filled + "░" * (bar_len - filled)

# ── Titles ────────────────────────────────────────────────────────────────────

TITLES = {
    5:   "Beginner",
    10:  "Street Hustler",
    15:  "Grinder",
    20:  "Entrepreneur",
    25:  "Investor",
    30:  "Dealmaker",
    40:  "Mogul",
    50:  "Tycoon",
    60:  "Elite",
    75:  "Mastermind",
    90:  "Kingpin",
    100: "Legendary",
}

def get_title(level: int) -> str | None:
    """Return the highest title earned at or below `level`."""
    earned = [title for req, title in TITLES.items() if level >= req]
    return earned[-1] if earned else None

def get_next_title(level: int) -> tuple[int, str] | None:
    """Return (levels_away, title_name) for the next milestone, or None if maxed."""
    upcoming = [(req, title) for req, title in TITLES.items() if req > level]
    if not upcoming:
        return None
    req, title = min(upcoming, key=lambda x: x[0])
    return req - level, title

# ── Access gates ──────────────────────────────────────────────────────────────

LEVEL_GATES = {
    "fish":       5,
    "mine":       3,
    "hunt":       5,
    "chop":       8,
    "scavenge":   10,
    "hack":       12,
    "farm":       15,
    "rob":        10,
    "gamble":     20,
    "blackjack":  25,
    "buy_stock":  30,
    "property":   20,
}

# Job tier level requirements (index matches JOBS list in economy.py)
JOB_LEVEL_GATES = [
    0,   # Unemployed
    1,   # Street Vendor
    2,   # Newspaper Delivery
    3,   # Janitor
    4,   # Cashier
    5,   # Fast Food Worker
    6,   # Warehouse Worker
    8,   # Delivery Driver
    10,  # Retail Manager
    12,  # Electrician
    14,  # Office Worker
    16,  # Mechanic
    18,  # Nurse
    20,  # Police Officer
    22,  # Pharmacist
    25,  # Engineer
    28,  # Software Developer
    31,  # Financial Analyst
    34,  # Accountant
    37,  # Architect
    40,  # Lawyer
    44,  # Surgeon
    48,  # Pilot
    52,  # Executive
    56,  # Investment Banker
    60,  # CEO
    65,  # Venture Capitalist
    70,  # Hedge Fund Manager
    75,  # Billionaire
]

# Prestige level requirements
PRESTIGE_LEVEL_GATES = {
    1: 25,
    2: 35,
    3: 45,
}
PRESTIGE_LEVEL_GATE_DEFAULT = 50  # prestige 4+

def prestige_level_required(current_prestige: int) -> int:
    return PRESTIGE_LEVEL_GATES.get(current_prestige + 1, PRESTIGE_LEVEL_GATE_DEFAULT)

# ── XP grant helper ───────────────────────────────────────────────────────────

async def grant_xp(user_id: int, amount: int) -> tuple[bool, int, int]:
    """
    Add XP to a user. Returns (leveled_up, old_level, new_level).
    Handles level-up internally (updates DB).
    """
    user = await db.get_user(user_id)
    old_xp = user.get("xp") or 0
    old_level = level_from_xp(old_xp)

    new_xp = min(old_xp + amount, total_xp_for_level(MAX_LEVEL))
    new_level = level_from_xp(new_xp)

    await db.set_xp(user_id, new_xp, new_level)

    return new_level > old_level, old_level, new_level