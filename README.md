# Vault — Discord Economy Bot

## Project Structure
```
Vault/
├── bot.py                  # Entry point
├── requirements.txt
├── .env.example            # Copy to .env and fill in your token
│
├── cogs/                   # Feature modules (add new features here)
│   ├── economy.py          # Core economy commands
│   ├── admin.py            # Admin-only commands
│   └── shop.py             # Shop system (expandable)
│
├── utils/                  # Shared utilities
│   ├── database.py         # All DB logic (aiosqlite)
│   ├── helpers.py          # Embed builders, formatting
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

3. Run the bot:
   ```bash
   python bot.py
   ```

## Commands

| Command | Description |
|---|---|
| `/balance` | Check wallet & bank |
| `/daily` | Claim daily reward |
| `/work` | Earn coins (1hr cooldown) |
| `/deposit` | Move coins to bank |
| `/withdraw` | Move coins to wallet |
| `/pay @user amount` | Send coins to someone |
| `/leaderboard` | Top richest members |
| `/shop` | Browse shop items |
| `/buy item` | Purchase an item |
| `/inventory` | View your items |
| `/addmoney` | [Admin] Give coins |
| `/removemoney` | [Admin] Remove coins |
| `/resetuser` | [Admin] Reset a user |

## Adding New Features

Add a new file in `cogs/`, then register it in `bot.py`:
```python
COGS = [
    "cogs.economy",
    "cogs.admin",
    "cogs.shop",
    "cogs.your_new_cog",   # ← add here
]
```
