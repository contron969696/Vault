# Vault — Discord Economy Bot

## Project Structure
```
Vault/
├── bot.py                  # Entry point
├── requirements.txt
├── .env.example            # Copy to .env and fill in your token
│
├── cogs/                   # Feature modules (add new features here)
│   ├── economy.py          # Core economy, jobs, skills, loot, prestige
│   ├── casino.py           # Blackjack, gamble, slots
│   ├── stocks.py           # Stock market (live S&P 500 prices)
│   ├── shop.py             # Tool shop, buy/sell
│   ├── admin.py            # Owner-only commands
│   └── help.py             # Auto-generated command list
│
├── utils/                  # Shared utilities
│   ├── database.py         # All DB logic (aiosqlite)
│   ├── migrations.py       # Schema versioning — add new columns safely
│   ├── helpers.py          # Embed builders, formatting, command registry
│   └── logger.py           # Rotating file + console logger
│
└── data/                   # Auto-created at runtime
    ├── vault.db            # SQLite database
    └── logs/vault.log      # Log files
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add your bot token:
   ```
   DISCORD_TOKEN=your_token_here
   ```

3. In `cogs/economy.py` and `cogs/admin.py`, replace `OWNER_ID` with your Discord user ID.

4. Run the bot:
   ```bash
   python bot.py
   ```

---

## Commands

### 💰 Economy
| Command | Description |
|---|---|
| `/balance` | Wallet, bank, loot value, stock value, net worth |
| `/profile` | Full stats — prestige, deaths, streak, job, finances |
| `/deposit` | Move coins to bank (blocked if bank is full) |
| `/withdraw` | Move coins to wallet |
| `/pay @user amount` | Send coins (10% tax) |
| `/leaderboard` | Top 10 richest members |
| `/jobs` | Browse all 29 job tiers |
| `/apply <job>` | Pay fee to upgrade your job |
| `/prestige` | Reset for +5% earnings per level (cost doubles each time) |

### ⚒️ Earning
| Command | Description |
|---|---|
| `/work` | Unscramble a word to earn coins (30 min cooldown) |
| `/daily` | Daily reward with streak bonuses (24hr cooldown) |
| `/weekly` | Weekly bonus (7 day cooldown) |
| `/beg` | Tiny payout (2 min cooldown) |

### 🎒 Skills
| Command | Description |
|---|---|
| `/fish` | Catch fish → loot inventory. Requires **Fishing Rod** |
| `/mine` | Mine ores → loot inventory. Requires **Pickaxe** |
| `/hunt` | Hunt animals → loot inventory. 5% death chance. Requires **Hunting Rifle** |
| `/chop` | Chop wood → loot inventory. Requires **Axe** |
| `/scavenge` | Scavenge junk → loot inventory. Requires **Scavenger Bag** |
| `/hack` | High risk/reward. 5% death chance. Requires **Hacking Laptop** |
| `/farm` | Plant crops, harvest in 1 hour. Requires **Tractor** |
| `/loot` | View your loot inventory |
| `/sell-loot <item> <qty>` | Sell loot items for coins |

### 🛒 Shop
| Command | Description |
|---|---|
| `/shop` | Browse all tools and prices |
| `/buy <item>` | Buy a tool (wallet only) |
| `/sell <item>` | Sell a tool for 50% of its value |
| `/inventory` | View owned tools |

### 👥 Social
| Command | Description |
|---|---|
| `/rob @user` | Steal from someone's wallet (1hr cooldown) |

### 🎰 Casino
| Command | Description |
|---|---|
| `/blackjack <bet>` | Full blackjack with hit, stand, double, split, surrender |
| `/gamble <bet>` | Roll a 12-sided dice vs Vault |
| `/slots <bet>` | 6-symbol slot machine (~44% win rate, 7% house edge) |

### 📈 Stocks
| Command | Description |
|---|---|
| `/stocks` | Browse all 10 stocks with live prices |
| `/buy-stock <ticker> <shares>` | Buy shares from wallet |
| `/sell-stock <ticker> <shares>` | Sell shares, proceeds to wallet |
| `/portfolio` | View holdings with profit/loss |

### 🔧 Admin (owner only, hidden from /help)
| Command | Description |
|---|---|
| `/addmoney @user amount` | Give coins to a member |
| `/removemoney @user amount` | Remove coins from a member |
| `/resetuser @user` | Wipe a member's entire data |

---

## Key Systems

### Bank Limit
- Starts at 500 coins
- Grows by 25% of every earning
- Deposits are blocked if bank is full
- Invest in stocks to park money outside the bank

### Prestige
- Requires enough wallet + bank wealth (doubles each prestige)
- Resets wallet, bank, job, and entire inventory
- Each level gives +5% to all earnings and casino wins

### Jobs (29 tiers)
- Apply costs come from wallet only
- Payout scales 1.3x per tier
- `/work` word difficulty scales with job tier

### Death
- `/hunt` and `/hack` have a 5% chance to kill you
- Death wipes your entire wallet (bank is safe)

### Stock Market
- 10 knockoff stocks tracking real S&P 500 prices via Yahoo Finance
- Prices update every hour in the background
- Stock value counts toward net worth in `/balance` and `/profile`

---

## Adding New Features

1. Create a new file in `cogs/`, e.g. `cogs/newfeature.py`
2. Add `@register_command("Category", "Description")` above each command
3. Register the cog in `bot.py` before `"cogs.help"`:
   ```python
   COGS = [
       "cogs.economy",
       "cogs.admin",
       "cogs.shop",
       "cogs.casino",
       "cogs.stocks",
       "cogs.your_new_cog",  # add here
       "cogs.help",          # must always be last
   ]
   ```
4. Add new database columns via a new migration in `utils/migrations.py`

## Adding Database Columns Safely

Never edit existing migrations. Add a new one at the bottom of the MIGRATIONS list:
```python
# Version N — description
"""
ALTER TABLE users ADD COLUMN new_column INTEGER DEFAULT 0;
""",
```
The bot applies it automatically on next startup without touching existing data.
