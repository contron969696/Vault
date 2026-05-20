import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import random
from utils.database import db
from utils.helpers import (
    economy_embed, error_embed, success_embed, info_embed,
    fmt_currency, register_command, apply_prestige
)
from utils.levels import (
    grant_xp, xp_progress, xp_bar, get_title, get_next_title,
    LEVEL_GATES, JOB_LEVEL_GATES, prestige_level_required
)

OWNER_ID = 453735929668960279  # <-- replace with your Discord user ID

DAILY_COOLDOWN    = 86400
WEEKLY_COOLDOWN   = 604800
WORK_COOLDOWN     = 1800
BEG_COOLDOWN      = 120
MINE_COOLDOWN     = 900
FISH_COOLDOWN     = 600
HUNT_COOLDOWN     = 1200
CHOP_COOLDOWN     = 900
SCAVENGE_COOLDOWN = 480
HACK_COOLDOWN     = 3600
FARM_HARVEST_TIME = 3600
ROB_COOLDOWN      = 3600

DAILY_BASE       = 200
WEEKLY_BASE      = 1500
MINIGAME_TIMEOUT = 20
DEATH_CHANCE     = 0.05

PRESTIGE_BASE_COST = 1_500_000

def prestige_cost(current_level: int) -> int:
    return PRESTIGE_BASE_COST * (2 ** current_level)

JOBS = [
    ("Unemployed",        0,          15,    35),
    ("Street Vendor",     200,        20,    46),
    ("Newspaper Delivery",600,        26,    60),
    ("Janitor",           1_500,      34,    78),
    ("Cashier",           3_000,      44,    101),
    ("Fast Food Worker",  6_000,      57,    131),
    ("Warehouse Worker",  12_000,     74,    170),
    ("Delivery Driver",   22_000,     96,    221),
    ("Retail Manager",    35_000,     125,   287),
    ("Electrician",       55_000,     163,   373),
    ("Office Worker",     80_000,     212,   485),
    ("Mechanic",          120_000,    276,   631),
    ("Nurse",             175_000,    359,   820),
    ("Police Officer",    250_000,    467,   1_066),
    ("Pharmacist",        350_000,    607,   1_386),
    ("Engineer",          500_000,    789,   1_802),
    ("Software Developer",700_000,    1_026, 2_343),
    ("Financial Analyst", 950_000,    1_334, 3_046),
    ("Accountant",        1_300_000,  1_734, 3_960),
    ("Architect",         1_750_000,  2_254, 5_148),
    ("Lawyer",            2_300_000,  2_930, 6_692),
    ("Surgeon",           3_200_000,  3_809, 8_700),
    ("Pilot",             4_200_000,  4_952, 11_310),
    ("Executive",         5_500_000,  6_438, 14_703),
    ("Investment Banker", 7_000_000,  8_369, 19_114),
    ("CEO",               9_000_000,  10_880,24_848),
    ("Venture Capitalist",11_500_000, 14_144,32_302),
    ("Hedge Fund Manager",14_500_000, 18_387,42_000),
    ("Billionaire",       18_000_000, 23_903,54_600),
]

JOB_MAP   = {j[0]: j for j in JOBS}
JOB_NAMES = [j[0] for j in JOBS]

WORD_TIERS = [
    ["cat","dog","run","box","cup"],
    ["apple","bread","stone","water","grape"],
    ["route","paper","carry","early","block"],
    ["broom","gloves","ladder","scrub","bucket"],
    ["price","queue","change","till","receipt"],
    ["burger","fridge","napkin","fryer","cashier"],
    ["pallet","forklift","crate","shift","loading"],
    ["parcel","diesel","mapper","rampway","route"],
    ["retail","stock","margin","target","upsell"],
    ["circuit","voltage","conduit","breaker","wiring"],
    ["report","budget","merger","folder","staple"],
    ["torque","gasket","piston","wrench","caliper"],
    ["triage","dosage","suture","syringe","patient"],
    ["patrol","warrant","dispatch","suspect","precinct"],
    ["dosage","compound","capsule","generic","refill"],
    ["tensile","thermal","modulus","circuit","torque"],
    ["syntax","kernel","buffer","lambda","pointer"],
    ["equity","futures","hedging","tranche","spread"],
    ["ledger","credit","deficit","accrual","amortize"],
    ["facade","blueprint","zoning","canopy","sectional"],
    ["clause","statute","motion","verdict","deponent"],
    ["scalpel","suction","sternum","cautery","retractor"],
    ["aileron","throttle","waypoint","descent","autopilot"],
    ["synergy","offshore","directive","pipeline","forecast"],
    ["leverage","tranche","warrant","arbitrage","covenant"],
    ["fiduciary","governance","shareholder","quarterly","directive"],
    ["portfolio","dilution","runway","valuation","termsheet"],
    ["volatility","derivative","liquidity","benchmark","rebalance"],
    ["conglomerate","acquisition","arbitrage","derivatives","shareholder"],
]

BEG_RESPONSES = [
    "A pigeon dropped a coin on you", "Someone tossed you spare change",
    "You found a crumpled bill under a bench", "A kind stranger helped you out",
    "You played air guitar on the sidewalk for tips",
    "A vending machine glitched and gave you a refund",
    "You found coins in a couch left on the curb",
    "A toddler handed you a coin before their parent noticed",
]

FISH_DROPS     = [("Minnow",0.35),("Bass",0.28),("Catfish",0.18),("Salmon",0.11),("Tuna",0.06),("Golden Fish",0.02)]
MINE_DROPS     = [("Coal",0.40),("Iron Ore",0.28),("Copper",0.16),("Silver",0.09),("Gold Nugget",0.05),("Gemstone",0.02)]
HUNT_DROPS     = [("Rabbit Pelt",0.38),("Turkey Feathers",0.27),("Deer Hide",0.18),("Boar Tusk",0.10),("Bear Fur",0.05),("Elk Antler",0.02)]
CHOP_DROPS     = [("Firewood",0.40),("Oak Lumber",0.27),("Pine Lumber",0.18),("Honeycomb",0.10),("Chest",0.04),("Ancient Carving",0.01)]
SCAVENGE_DROPS = [("Phone Parts",0.38),("Scrap Metal",0.28),("Old Microwave",0.18),("Loose Change",0.10),("Vintage Item",0.05),("Collector's Item",0.01)]
FARM_CROPS     = [(200,0.40),(450,0.28),(900,0.18),(1800,0.10),(4000,0.04)]
ROB_OUTCOMES   = [("caught",0,0.50),("small",0.10,0.30),("medium",0.25,0.15),("jackpot",0.75,0.05)]

ROB_FINE_MIN, ROB_FINE_MAX   = 50, 200
ROB_MIN_WALLET               = 100
HACK_SUCCESS                 = 0.60
HACK_FINE_MIN, HACK_FINE_MAX = 100, 400

def weighted_loot(drops):
    names, weights = zip(*drops)
    return random.choices(names, weights=weights, k=1)[0]

def weighted_value(results):
    entries = [r[:-1] for r in results]
    weights = [r[-1] for r in results]
    return random.choices(entries, weights=weights, k=1)[0]

def cooldown_remaining(last_str, cooldown):
    if not last_str:
        return None
    diff = (datetime.utcnow() - datetime.fromisoformat(last_str)).total_seconds()
    return max(0, cooldown - diff) if diff < cooldown else None

def fmt_cd(seconds):
    h, r = divmod(int(seconds), 3600)
    m = r // 60
    s = r % 60
    if h > 0:   return f"{h}h {m}m"
    if m > 0:   return f"{m}m {s}s"
    return f"{s}s"

async def require_item(interaction, item_name):
    if not await db.has_item(interaction.user.id, item_name):
        await interaction.response.send_message(
            embed=error_embed("Missing Equipment", f"You need a **{item_name}** to use this.\nBuy one from `/shop`."),
            ephemeral=False
        )
        return False
    return True

async def check_cooldown(interaction, last_str, cooldown, label):
    if interaction.user.id == OWNER_ID:
        return True
    remaining = cooldown_remaining(last_str, cooldown)
    if remaining:
        await interaction.response.send_message(
            embed=error_embed("On Cooldown", f"**{label}** available again in **{fmt_cd(remaining)}**."),
            ephemeral=False
        )
        return False
    return True

async def check_level(interaction, gate_key: str) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    required = LEVEL_GATES.get(gate_key, 0)
    if required == 0:
        return True
    user  = await db.get_user(interaction.user.id)
    level = user.get("level") or 1
    if level < required:
        await interaction.response.send_message(
            embed=error_embed(
                "Level Too Low",
                f"You need to be **Level {required}** to use this.\nYou are currently Level {level}."
            ),
            ephemeral=False
        )
        return False
    return True

async def handle_death(interaction, lost: int):
    embed = discord.Embed(
        title="💀 You Died!",
        description=f"You lost all **{fmt_currency(lost)}** in your wallet.\n*Your bank savings are safe.*",
        color=0x000000
    )
    embed.set_footer(text="Better luck next time.")
    await interaction.response.send_message(embed=embed)

async def maybe_announce_levelup(interaction, leveled_up: bool, new_level: int):
    if not leveled_up:
        return
    from utils.levels import get_title, TITLES
    title     = get_title(new_level)
    title_str = f"\nYou earned the title **\"{title}\"**! 🏆" if new_level in TITLES else ""
    await interaction.followup.send(
        embed=discord.Embed(
            title=f"⬆️ Level Up! You're now Level {new_level}!",
            description=f"Keep grinding to unlock more commands and job tiers.{title_str}",
            color=0xF1C40F
        ),
        ephemeral=False
    )


class UnscrambleView(discord.ui.View):

    def __init__(self, correct, options, earned, job_name, user_id):
        super().__init__(timeout=MINIGAME_TIMEOUT)
        self.correct  = correct
        self.earned   = earned
        self.job_name = job_name
        self.user_id  = user_id
        self.result   = None
        for option in options:
            btn          = discord.ui.Button(label=option, style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(option)
            self.add_item(btn)

    def make_callback(self, word):
        async def callback(interaction):
            self.result = (word == self.correct)
            self.stop()
            if self.result:
                await db.update_balance(interaction.user.id, self.earned)
                await db.log_transaction(interaction.user.id, self.earned, "work")
                await db.grow_bank_limit(interaction.user.id, self.earned)
                xp = 20 + (self.earned // 100)
                leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
                embed = success_embed("Correct!", f"**{self.correct}** — You earned {fmt_currency(self.earned)} as **{self.job_name}**.\n+{xp} XP")
            else:
                embed = error_embed("Wrong!", f"The word was **{self.correct}**. No pay this shift.")
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            if self.result:
                await maybe_announce_levelup(interaction, leveled_up, new_level)
        return callback


class Economy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Check your wallet and bank balance.")
    @app_commands.describe(member="The member to check (leave empty for yourself)")
    @register_command("Economy", "Check wallet, bank, net worth, and current job.")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target    = member or interaction.user
        user      = await db.get_user(target.id)
        loot_val  = await db.get_loot_value(target.id)
        tool_val  = await db.get_tool_value(target.id)
        prop_val  = await db.get_property_value(target.id)
        job       = user.get("job") or "Unemployed"
        prestige  = user.get("prestige") or 0
        bank_limit= user.get("bank_limit") or 500
        stock_val = await db.get_portfolio_value(target.id)
        net_worth = user["balance"] + user["bank"] + loot_val + tool_val + stock_val + prop_val

        embed = economy_embed(
            f"{target.display_name}'s Balance",
            f"**Wallet:** {fmt_currency(user['balance'])}\n"
            f"**Bank:** {fmt_currency(user['bank'])} / {fmt_currency(bank_limit)}\n"
            f"**Loot Value:** {fmt_currency(loot_val)}\n"
            f"**Tool Value:** {fmt_currency(tool_val)}\n"
            f"**Property Value:** {fmt_currency(prop_val)}\n"
            f"**Stocks:** {fmt_currency(stock_val)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**Net Worth:** {fmt_currency(net_worth)}\n"
            f"**Job:** {job}\n"
            f"**Prestige:** ⭐ {prestige}"
        )
        embed.color = 0x2ECC71
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="profile", description="View your full profile and stats.")
    @app_commands.describe(member="The member to check (leave empty for yourself)")
    @register_command("Economy", "View your full stats — prestige, deaths, streak, net worth, XP, and more.")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target    = member or interaction.user
        user      = await db.get_user(target.id)
        loot_val  = await db.get_loot_value(target.id)
        tool_val  = await db.get_tool_value(target.id)
        prop_val  = await db.get_property_value(target.id)
        prestige  = user.get("prestige") or 0
        mult      = 1.0 + prestige * 0.05
        bank_limit= user.get("bank_limit") or 500
        stock_val = await db.get_portfolio_value(target.id)
        net_worth = user["balance"] + user["bank"] + loot_val + tool_val + stock_val + prop_val

        total_xp              = user.get("xp") or 0
        level, xp_into, xp_needed = xp_progress(total_xp)
        bar                   = xp_bar(xp_into, xp_needed)
        title                 = get_title(level)
        next_title_info       = get_next_title(level)
        title_str             = f'"{title}"' if title else "None yet"

        if xp_needed == 0:
            xp_line  = "MAX LEVEL"
            bar_line = "█" * 20
        else:
            pct      = int((xp_into / xp_needed) * 100)
            xp_line  = f"{xp_into:,} / {xp_needed:,} XP ({pct}%)"
            bar_line = f"[{bar}]"

        next_title_str = ""
        if next_title_info:
            levels_away, next_name = next_title_info
            next_title_str = f"\nNext title: **\"{next_name}\"** in {levels_away} level{'s' if levels_away != 1 else ''}"

        embed = discord.Embed(title=f"📋 {target.display_name}'s Profile", color=0x9B59B6)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💰 Finances", value=(
            f"Wallet: {fmt_currency(user['balance'])}\n"
            f"Bank: {fmt_currency(user['bank'])} / {fmt_currency(bank_limit)}\n"
            f"Stocks: {fmt_currency(stock_val)}\n"
            f"Properties: {fmt_currency(prop_val)}\n"
            f"Net Worth: {fmt_currency(net_worth)}"
        ), inline=True)
        embed.add_field(name="⭐ Prestige", value=(
            f"Level: {prestige}\n"
            f"Earnings Bonus: +{int((mult - 1) * 100)}%\n"
            f"Next Prestige: {fmt_currency(prestige_cost(prestige))}"
        ), inline=True)
        embed.add_field(name="📊 Stats", value=(
            f"Job: {user.get('job') or 'Unemployed'}\n"
            f"Daily Streak: 🔥 {user.get('daily_streak') or 0}\n"
            f"Deaths: 💀 {user.get('deaths') or 0}"
        ), inline=True)
        embed.add_field(name=f"🎖️ Level {level} — {title_str}", value=(
            f"{bar_line}\n"
            f"{xp_line}"
            f"{next_title_str}"
        ), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="prestige", description="Prestige if you have enough wealth.")
    @register_command("Economy", "Reset your progress for +5% earnings per prestige level.")
    async def prestige_cmd(self, interaction: discord.Interaction):
        user    = await db.get_user(interaction.user.id)
        current = user.get("prestige") or 0
        cost    = prestige_cost(current)

        level_req = prestige_level_required(current)
        level     = user.get("level") or 1
        if level < level_req:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Level Too Low",
                    f"You need to be **Level {level_req}** to reach Prestige {current + 1}.\n"
                    f"You are currently Level {level}."
                ),
                ephemeral=False
            )

        net_worth = user["balance"] + user["bank"]
        if net_worth < cost:
            needed = cost - net_worth
            return await interaction.response.send_message(
                embed=error_embed("Not Ready",
                    f"You need **{fmt_currency(cost)}** in wallet + bank to reach Prestige {current + 1}.\n"
                    f"You are {fmt_currency(needed)} short."),
                ephemeral=False
            )

        await db.prestige(interaction.user.id)
        new_bonus  = int((current + 1) * 5)
        next_cost  = prestige_cost(current + 1)
        next_level = prestige_level_required(current + 1)

        embed = discord.Embed(
            title="⭐ Prestige Unlocked!",
            description=(
                f"You are now **Prestige {current + 1}**.\n\n"
                f"Your wallet, bank, and entire inventory have been reset.\n"
                f"Your job has been reset to Unemployed.\n\n"
                f"**Earnings bonus: +{new_bonus}% on all earnings and casino wins.**\n"
                f"Next prestige costs: {fmt_currency(next_cost)} · Requires Level {next_level}"
            ),
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily reward.")
    @register_command("Earning", "Claim daily coins. Streak bonuses stack up to 30 days.")
    async def daily(self, interaction: discord.Interaction):
        user = await db.get_user(interaction.user.id)
        now  = datetime.utcnow()
        if not await check_cooldown(interaction, user["last_daily"], DAILY_COOLDOWN, "/daily"):
            return
        streak = user.get("daily_streak") or 0
        if user["last_daily"]:
            hours  = (now - datetime.fromisoformat(user["last_daily"])).total_seconds() / 3600
            streak = streak + 1 if hours < 48 else 1
        else:
            streak = 1
        bonus  = min(streak - 1, 30) * 20
        amount = apply_prestige(DAILY_BASE + bonus, user.get("prestige") or 0)
        await db.update_balance(interaction.user.id, amount)
        await db.set_field(interaction.user.id, "last_daily", now.isoformat())
        await db.set_field(interaction.user.id, "daily_streak", streak)
        await db.log_transaction(interaction.user.id, amount, "daily")
        await db.grow_bank_limit(interaction.user.id, amount)
        xp = min(50 + streak * 5, 200)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        streak_text = f"\n🔥 {streak} day streak (+{fmt_currency(bonus)} bonus)" if streak > 1 else ""
        await interaction.response.send_message(
            embed=success_embed("Daily Claimed!", f"You received {fmt_currency(amount)}!{streak_text}\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="weekly", description="Claim your weekly reward.")
    @register_command("Earning", "Claim your weekly bonus coins.")
    async def weekly(self, interaction: discord.Interaction):
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_weekly"), WEEKLY_COOLDOWN, "/weekly"):
            return
        amount = apply_prestige(WEEKLY_BASE, user.get("prestige") or 0)
        await db.update_balance(interaction.user.id, amount)
        await db.set_field(interaction.user.id, "last_weekly", datetime.utcnow().isoformat())
        await db.log_transaction(interaction.user.id, amount, "weekly")
        await db.grow_bank_limit(interaction.user.id, amount)
        xp = 200
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=success_embed("Weekly Claimed!", f"You received {fmt_currency(amount)}!\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="beg", description="Beg for some coins. 2 min cooldown.")
    @register_command("Earning", "Beg for a tiny payout. 2 min cooldown.")
    async def beg(self, interaction: discord.Interaction):
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_beg"), BEG_COOLDOWN, "/beg"):
            return
        amount = apply_prestige(random.randint(2, 15), user.get("prestige") or 0)
        await db.update_balance(interaction.user.id, amount)
        await db.set_field(interaction.user.id, "last_beg", datetime.utcnow().isoformat())
        await db.log_transaction(interaction.user.id, amount, "beg")
        await db.grow_bank_limit(interaction.user.id, amount)
        xp = 5
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("Begging...", f"{random.choice(BEG_RESPONSES)} — you got {fmt_currency(amount)}.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="work", description="Work your shift. Unscramble a word to get paid.")
    @register_command("Earning", "Unscramble a word to earn coins. Payout scales with your job tier.")
    async def work(self, interaction: discord.Interaction):
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user["last_work"], WORK_COOLDOWN, "/work"):
            return
        job_name  = user.get("job") or "Unemployed"
        job       = JOB_MAP.get(job_name, JOBS[0])
        _, _, mn, mx = job
        earned    = apply_prestige(random.randint(mn, mx), user.get("prestige") or 0)
        tier      = JOB_NAMES.index(job_name)
        pool      = WORD_TIERS[tier]
        await db.set_field(interaction.user.id, "last_work", datetime.utcnow().isoformat())
        correct   = random.choice(pool)
        scrambled = list(correct)
        while "".join(scrambled) == correct:
            random.shuffle(scrambled)
        wrong   = random.sample([w for w in pool if w != correct], min(3, len(pool) - 1))
        options = wrong + [correct]
        random.shuffle(options)
        embed = info_embed(
            f"Work Shift — {job_name}",
            f"Unscramble to earn {fmt_currency(earned)}:\n\n# **{''.join(scrambled).upper()}**\n\n*{MINIGAME_TIMEOUT}s to answer.*"
        )
        view = UnscrambleView(correct, options, earned, job_name, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        await view.wait()
        if view.result is None:
            for child in view.children:
                child.disabled = True
            await interaction.edit_original_response(
                embed=error_embed("Too Slow!", f"The word was **{correct}**. No pay."), view=view
            )

    @app_commands.command(name="jobs", description="Browse all jobs and their salaries.")
    @register_command("Economy", "Browse all job tiers, salaries, application costs, and level requirements.")
    async def jobs(self, interaction: discord.Interaction):
        user    = await db.get_user(interaction.user.id)
        current = user.get("job") or "Unemployed"
        level   = user.get("level") or 1
        lines   = []
        for i, (name, cost, mn, mx) in enumerate(JOBS):
            marker   = "▶ " if name == current else "  "
            cost_str = f"Apply: {fmt_currency(cost)}" if cost > 0 else "Starting job"
            lvl_req  = JOB_LEVEL_GATES[i]
            locked   = "🔒 " if level < lvl_req else ""
            lvl_str  = f" · Lvl {lvl_req}" if lvl_req > 0 else ""
            lines.append(f"{marker}{locked}**{name}** — {fmt_currency(mn)}–{fmt_currency(mx)}/shift · {cost_str}{lvl_str}")
        await interaction.response.send_message(
            embed=info_embed("📋 Job Listings", "\n".join(lines) + "\n\nUse `/apply <job name>` to apply."),
            ephemeral=False
        )

    @app_commands.command(name="apply", description="Apply for a higher-tier job.")
    @app_commands.describe(job_name="The exact name of the job")
    @register_command("Economy", "Pay a fee from your wallet to upgrade to a better job.")
    async def apply(self, interaction: discord.Interaction, job_name: str):
        matched = next((j for j in JOBS if j[0].lower() == job_name.lower()), None)
        if not matched:
            return await interaction.response.send_message(
                embed=error_embed("Not Found", f"No job called **{job_name}**. Use `/jobs`."), ephemeral=False
            )
        name, cost, mn, mx = matched
        user    = await db.get_user(interaction.user.id)
        current = user.get("job") or "Unemployed"
        level   = user.get("level") or 1
        if current.lower() == name.lower():
            return await interaction.response.send_message(
                embed=error_embed("Already Employed", f"You already work as **{name}**."), ephemeral=False
            )
        cur_idx = JOB_NAMES.index(current) if current in JOB_NAMES else 0
        new_idx = JOB_NAMES.index(name)
        if new_idx <= cur_idx:
            return await interaction.response.send_message(
                embed=error_embed("Downgrade Not Allowed", "You can only upgrade jobs."), ephemeral=False
            )
        lvl_req = JOB_LEVEL_GATES[new_idx]
        if level < lvl_req:
            return await interaction.response.send_message(
                embed=error_embed("Level Too Low", f"**{name}** requires Level {lvl_req}. You are Level {level}."),
                ephemeral=False
            )
        if user["balance"] < cost:
            short = cost - user["balance"]
            msg   = f"Applying for **{name}** costs {fmt_currency(cost)} from your wallet.\nYou need {fmt_currency(short)} more."
            if user["bank"] >= short:
                msg += f"\n\nYou have enough in your bank — use `/withdraw` first."
            return await interaction.response.send_message(
                embed=error_embed("Insufficient Wallet Funds", msg), ephemeral=False
            )
        await db.update_balance(interaction.user.id, -cost)
        await db.set_job(interaction.user.id, name)
        await db.log_transaction(interaction.user.id, -cost, f"apply_{name}")
        await interaction.response.send_message(
            embed=success_embed("Hired!", f"You are now a **{name}**.\nFee: {fmt_currency(cost)} · Salary: {fmt_currency(mn)}–{fmt_currency(mx)}/shift")
        )

    @app_commands.command(name="fish", description="Cast your line. Requires a Fishing Rod.")
    @register_command("Skills", "Catch fish that go into your inventory to sell later. Requires **Fishing Rod**.")
    async def fish(self, interaction: discord.Interaction):
        if not await check_level(interaction, "fish"): return
        if not await require_item(interaction, "Fishing Rod"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_fish"), FISH_COOLDOWN, "/fish"): return
        loot = weighted_loot(FISH_DROPS)
        await db.add_loot(interaction.user.id, loot)
        await db.set_field(interaction.user.id, "last_fish", datetime.utcnow().isoformat())
        from utils.database import LOOT_ITEMS
        sell_val = next((l[2] for l in LOOT_ITEMS if l[0] == loot), 0)
        xp = 15 + (sell_val // 50)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("🎣 Fishing", f"You caught a **{loot}**! Added to inventory.\nUse `/sell-loot {loot} 1` to sell it.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="mine", description="Dig for ores. Requires a Pickaxe.")
    @register_command("Skills", "Mine for ores that go into your inventory. Requires **Pickaxe**.")
    async def mine(self, interaction: discord.Interaction):
        if not await check_level(interaction, "mine"): return
        if not await require_item(interaction, "Pickaxe"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_mine"), MINE_COOLDOWN, "/mine"): return
        loot = weighted_loot(MINE_DROPS)
        await db.add_loot(interaction.user.id, loot)
        await db.set_field(interaction.user.id, "last_mine", datetime.utcnow().isoformat())
        from utils.database import LOOT_ITEMS
        sell_val = next((l[2] for l in LOOT_ITEMS if l[0] == loot), 0)
        xp = 15 + (sell_val // 50)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("⛏️ Mining", f"You mined **{loot}**! Added to inventory.\nUse `/sell-loot {loot} 1` to sell it.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="hunt", description="Hunt for game. Requires a Hunting Rifle. Risk of death!")
    @register_command("Skills", "Hunt animals for pelts. 5% death chance (lose wallet). Requires **Hunting Rifle**.")
    async def hunt(self, interaction: discord.Interaction):
        if not await check_level(interaction, "hunt"): return
        if not await require_item(interaction, "Hunting Rifle"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_hunt"), HUNT_COOLDOWN, "/hunt"): return
        await db.set_field(interaction.user.id, "last_hunt", datetime.utcnow().isoformat())
        if random.random() < DEATH_CHANCE:
            lost = user["balance"]
            await db.wipe_wallet(interaction.user.id)
            await db.log_transaction(interaction.user.id, -lost, "death_hunt")
            return await handle_death(interaction, lost)
        loot = weighted_loot(HUNT_DROPS)
        await db.add_loot(interaction.user.id, loot)
        from utils.database import LOOT_ITEMS
        sell_val = next((l[2] for l in LOOT_ITEMS if l[0] == loot), 0)
        xp = 30 + (sell_val // 50)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("🏹 Hunting", f"You obtained **{loot}**! Added to inventory.\nUse `/sell-loot {loot} 1` to sell it.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="chop", description="Chop wood. Requires an Axe.")
    @register_command("Skills", "Chop wood and collect lumber. Requires **Axe**.")
    async def chop(self, interaction: discord.Interaction):
        if not await check_level(interaction, "chop"): return
        if not await require_item(interaction, "Axe"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_chop"), CHOP_COOLDOWN, "/chop"): return
        loot = weighted_loot(CHOP_DROPS)
        await db.add_loot(interaction.user.id, loot)
        await db.set_field(interaction.user.id, "last_chop", datetime.utcnow().isoformat())
        from utils.database import LOOT_ITEMS
        sell_val = next((l[2] for l in LOOT_ITEMS if l[0] == loot), 0)
        xp = 15 + (sell_val // 50)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("🪓 Chopping", f"You collected **{loot}**! Added to inventory.\nUse `/sell-loot {loot} 1` to sell it.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="scavenge", description="Dumpster dive. Requires a Scavenger Bag.")
    @register_command("Skills", "Scavenge for junk to sell. Requires **Scavenger Bag**.")
    async def scavenge(self, interaction: discord.Interaction):
        if not await check_level(interaction, "scavenge"): return
        if not await require_item(interaction, "Scavenger Bag"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_scavenge"), SCAVENGE_COOLDOWN, "/scavenge"): return
        loot = weighted_loot(SCAVENGE_DROPS)
        await db.add_loot(interaction.user.id, loot)
        await db.set_field(interaction.user.id, "last_scavenge", datetime.utcnow().isoformat())
        from utils.database import LOOT_ITEMS
        sell_val = next((l[2] for l in LOOT_ITEMS if l[0] == loot), 0)
        xp = 15 + (sell_val // 50)
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=economy_embed("🗑️ Scavenging", f"You found **{loot}**! Added to inventory.\nUse `/sell-loot {loot} 1` to sell it.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="hack", description="High-risk high-reward. Requires a Hacking Laptop. Risk of death!")
    @register_command("Skills", "60% payout, 35% fine, 5% death. Requires **Hacking Laptop**.")
    async def hack(self, interaction: discord.Interaction):
        if not await check_level(interaction, "hack"): return
        if not await require_item(interaction, "Hacking Laptop"): return
        user = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, user.get("last_hack"), HACK_COOLDOWN, "/hack"): return
        await db.set_field(interaction.user.id, "last_hack", datetime.utcnow().isoformat())
        roll = random.random()
        if roll < DEATH_CHANCE:
            lost = user["balance"]
            await db.wipe_wallet(interaction.user.id)
            await db.log_transaction(interaction.user.id, -lost, "death_hack")
            return await handle_death(interaction, lost)
        if roll < HACK_SUCCESS + DEATH_CHANCE:
            amount = apply_prestige(random.randint(300, 1200), user.get("prestige") or 0)
            await db.update_balance(interaction.user.id, amount)
            await db.log_transaction(interaction.user.id, amount, "hack_success")
            await db.grow_bank_limit(interaction.user.id, amount)
            xp = 30 + (amount // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await interaction.response.send_message(
                embed=success_embed("Hack Successful! 💻", f"You siphoned {fmt_currency(amount)} from the system.\n+{xp} XP")
            )
            await maybe_announce_levelup(interaction, leveled_up, new_level)
        else:
            fine = min(random.randint(HACK_FINE_MIN, HACK_FINE_MAX), user["balance"])
            await db.update_balance(interaction.user.id, -fine)
            await db.log_transaction(interaction.user.id, -fine, "hack_caught")
            await interaction.response.send_message(
                embed=error_embed("Caught! 🚨", f"You tripped the firewall and were fined {fmt_currency(fine)}.")
            )

    @app_commands.command(name="farm", description="Plant crops and harvest in 1 hour. Requires a Tractor.")
    @register_command("Skills", "Plant crops, come back in 1 hour to harvest. Requires **Tractor**.")
    async def farm(self, interaction: discord.Interaction):
        if not await check_level(interaction, "farm"): return
        if not await require_item(interaction, "Tractor"): return
        user = await db.get_user(interaction.user.id)
        now  = datetime.utcnow()
        if user.get("farm_planted"):
            planted_at = datetime.fromisoformat(user["farm_planted"])
            elapsed    = (now - planted_at).total_seconds()
            if elapsed < FARM_HARVEST_TIME:
                return await interaction.response.send_message(
                    embed=info_embed("🌾 Growing...", f"Come back in **{fmt_cd(FARM_HARVEST_TIME - elapsed)}** to harvest."),
                    ephemeral=False
                )
            amount = apply_prestige(user.get("farm_amount") or 0, user.get("prestige") or 0)
            await db.update_balance(interaction.user.id, amount)
            await db.set_field(interaction.user.id, "farm_planted", None)
            await db.set_field(interaction.user.id, "farm_amount", 0)
            await db.log_transaction(interaction.user.id, amount, "farm_harvest")
            await db.grow_bank_limit(interaction.user.id, amount)
            xp = 25 + (amount // 200)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await interaction.response.send_message(
                embed=success_embed("🌾 Harvested!", f"You earned {fmt_currency(amount)}!\n+{xp} XP")
            )
            await maybe_announce_levelup(interaction, leveled_up, new_level)
            return
        amount = weighted_value(FARM_CROPS)[0]
        await db.set_field(interaction.user.id, "farm_planted", now.isoformat())
        await db.set_field(interaction.user.id, "farm_amount", amount)
        await interaction.response.send_message(
            embed=economy_embed("🌱 Planted!", "Come back in **1 hour** to harvest your crops!")
        )

    @app_commands.command(name="sell-loot", description="Sell items from your loot inventory.")
    @app_commands.describe(item_name="Name of the loot item", quantity="How many to sell")
    @register_command("Skills", "Sell loot items collected from fishing, mining, hunting, etc.")
    async def sell_loot(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        if quantity <= 0:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Quantity must be at least 1."), ephemeral=False
            )
        success, total = await db.sell_loot(interaction.user.id, item_name, quantity)
        if not success:
            return await interaction.response.send_message(
                embed=error_embed("Can't Sell", f"You don't have {quantity}x **{item_name}** in your inventory.\nCheck `/loot` to see what you have."),
                ephemeral=False
            )
        await db.log_transaction(interaction.user.id, total, f"sell_loot_{item_name}")
        await db.grow_bank_limit(interaction.user.id, total)
        xp = 10
        leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
        await interaction.response.send_message(
            embed=success_embed("Sold!", f"You sold {quantity}x **{item_name}** for {fmt_currency(total)}.\n+{xp} XP")
        )
        await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="loot", description="View your loot inventory.")
    @register_command("Skills", "View all loot items you've collected from skill commands.")
    async def loot(self, interaction: discord.Interaction):
        items = await db.get_loot_inventory(interaction.user.id)
        if not items:
            return await interaction.response.send_message(
                embed=info_embed("🎒 Loot Inventory", "Your loot bag is empty.\nUse skill commands like `/fish`, `/mine`, `/hunt` to collect items."),
                ephemeral=False
            )
        categories = {}
        for item in items:
            cat = item["category"].capitalize()
            categories.setdefault(cat, []).append(item)
        lines = []
        for cat, cat_items in categories.items():
            lines.append(f"**{cat}**")
            for item in cat_items:
                lines.append(f"  {item['name']} x{item['quantity']} — sell: {fmt_currency(item['sell_value'])} each")
        lines.append(f"\nTotal value: {fmt_currency(await db.get_loot_value(interaction.user.id))}")
        lines.append("Use `/sell-loot <name> <qty>` to sell.")
        await interaction.response.send_message(
            embed=info_embed("🎒 Loot Inventory", "\n".join(lines)), ephemeral=False
        )

    @app_commands.command(name="rob", description="Attempt to rob another player.")
    @app_commands.describe(member="Who to rob")
    @register_command("Social", "Try to steal from another player's wallet. 50% chance of a fine.")
    async def rob(self, interaction: discord.Interaction, member: discord.Member):
        if not await check_level(interaction, "rob"): return
        if member.bot or member.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Can't rob yourself or a bot."), ephemeral=False
            )
        robber = await db.get_user(interaction.user.id)
        if not await check_cooldown(interaction, robber.get("last_rob"), ROB_COOLDOWN, "/rob"): return
        target = await db.get_user(member.id)
        if target["balance"] < ROB_MIN_WALLET:
            return await interaction.response.send_message(
                embed=error_embed("Not Worth It", f"{member.display_name} only has {fmt_currency(target['balance'])}. Min is {fmt_currency(ROB_MIN_WALLET)}."),
                ephemeral=False
            )
        await db.set_field(interaction.user.id, "last_rob", datetime.utcnow().isoformat())
        entries       = [r[:-1] for r in ROB_OUTCOMES]
        weights       = [r[-1]  for r in ROB_OUTCOMES]
        outcome_label, steal_pct = random.choices(entries, weights=weights, k=1)[0]
        if outcome_label == "caught":
            fine = min(random.randint(ROB_FINE_MIN, ROB_FINE_MAX), robber["balance"])
            await db.update_balance(interaction.user.id, -fine)
            await db.log_transaction(interaction.user.id, -fine, "rob_caught")
            await interaction.response.send_message(
                embed=error_embed("Caught! 🚨", f"You got caught robbing **{member.display_name}** and were fined {fmt_currency(fine)}.")
            )
        else:
            stolen = max(1, int(target["balance"] * steal_pct))
            await db.update_balance(member.id, -stolen)
            await db.update_balance(interaction.user.id, stolen)
            await db.log_transaction(interaction.user.id, stolen, "rob_success")
            await db.log_transaction(member.id, -stolen, "rob_victim")
            flavor = {0.10: "You pickpocketed them.", 0.25: "You threatened them and got away.", 0.75: "You pulled off a flawless heist!"}[steal_pct]
            xp = 40
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await interaction.response.send_message(
                embed=success_embed("Robbery! 🦹", f"{flavor}\nStole {fmt_currency(stolen)} ({int(steal_pct*100)}%) from **{member.display_name}**.\n+{xp} XP")
            )
            await maybe_announce_levelup(interaction, leveled_up, new_level)

    @app_commands.command(name="pay", description="Send coins to another member.")
    @app_commands.describe(member="Who to pay", amount="How much to send")
    @register_command("Social", "Send coins from your wallet to another member.")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot or member.id == interaction.user.id:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Can't pay yourself or a bot."), ephemeral=False
            )
        user = await db.get_user(interaction.user.id)
        if amount <= 0 or amount > user["balance"]:
            return await interaction.response.send_message(
                embed=error_embed("Insufficient Funds", "Not enough in your wallet."), ephemeral=False
            )
        tax      = max(1, int(amount * 0.10))
        received = amount - tax
        await db.update_balance(interaction.user.id, -amount)
        await db.update_balance(member.id, received)
        await db.log_transaction(interaction.user.id, -amount, "pay_out")
        await db.log_transaction(member.id, received, "pay_in")
        await interaction.response.send_message(embed=success_embed(
            "Sent!",
            f"{interaction.user.mention} → {member.mention}\n"
            f"**Sent:** {fmt_currency(amount)}\n"
            f"**Tax (10%):** -{fmt_currency(tax)}\n"
            f"**Received:** {fmt_currency(received)}"
        ))

    @app_commands.command(name="deposit", description="Deposit coins into your bank.")
    @app_commands.describe(amount="Amount to deposit, or 'all'")
    @register_command("Economy", "Move coins from your wallet to your bank for safekeeping.")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        user = await db.get_user(interaction.user.id)
        amt  = user["balance"] if amount.lower() == "all" else (int(amount) if amount.isdigit() else -1)
        if amt <= 0 or amt > user["balance"]:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Use a number or `all`."), ephemeral=False
            )
        await db.update_balance(interaction.user.id, -amt)
        success, space = await db.update_bank_safe(interaction.user.id, amt)
        if not success:
            await db.update_balance(interaction.user.id, amt)
            return await interaction.response.send_message(
                embed=error_embed("Bank Full",
                    f"Your bank can only hold {fmt_currency(space)} more coins.\n"
                    f"Earn more to expand your bank limit, or invest in /stocks."),
                ephemeral=False
            )
        await interaction.response.send_message(
            embed=success_embed("Deposited", f"Moved {fmt_currency(amt)} to your bank.")
        )

    @app_commands.command(name="withdraw", description="Withdraw coins from your bank.")
    @app_commands.describe(amount="Amount to withdraw, or 'all'")
    @register_command("Economy", "Move coins from your bank back to your wallet.")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        user = await db.get_user(interaction.user.id)
        amt  = user["bank"] if amount.lower() == "all" else (int(amount) if amount.isdigit() else -1)
        if amt <= 0 or amt > user["bank"]:
            return await interaction.response.send_message(
                embed=error_embed("Invalid", "Use a number or `all`."), ephemeral=False
            )
        await db.update_bank(interaction.user.id, -amt)
        await db.update_balance(interaction.user.id, amt)
        await interaction.response.send_message(
            embed=success_embed("Withdrawn", f"Moved {fmt_currency(amt)} to your wallet.")
        )

    @app_commands.command(name="leaderboard", description="See the richest members.")
    @register_command("Social", "Top 10 richest members by wallet + bank balance.")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await db.get_leaderboard()
        if not rows:
            return await interaction.response.send_message(
                embed=error_embed("Empty", "No data yet."), ephemeral=False
            )
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, row in enumerate(rows):
            u    = await self.bot.fetch_user(row["user_id"])
            name = u.display_name if u else f"User {row['user_id']}"
            lines.append(f"{medals[i] if i < 3 else f'`{i+1}.`'} **{name}** — {fmt_currency(row['total'])}")
        await interaction.response.send_message(embed=economy_embed("Leaderboard", "\n".join(lines)))


async def setup(bot):
    await bot.add_cog(Economy(bot))