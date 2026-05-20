import aiosqlite
import logging

logger = logging.getLogger("vault")

MIGRATIONS = [
    # Version 1 — initial schema
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        bank    INTEGER DEFAULT 0,
        xp      INTEGER DEFAULT 0,
        level   INTEGER DEFAULT 1,
        last_daily TEXT DEFAULT NULL,
        last_work  TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS shop_items (
        item_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        description TEXT,
        price       INTEGER NOT NULL,
        role_id     INTEGER DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS inventories (
        user_id  INTEGER NOT NULL,
        item_id  INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        amount    INTEGER NOT NULL,
        type      TEXT NOT NULL,
        timestamp TEXT DEFAULT (datetime('now'))
    );
    """,

    # Version 2 — job system
    """
    ALTER TABLE users ADD COLUMN job TEXT DEFAULT 'Unemployed';
    """,

    # Version 3 — skill cooldowns, streaks, farm
    """
    ALTER TABLE users ADD COLUMN daily_streak   INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN last_weekly    TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_mine      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_fish      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_hunt      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_chop      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_scavenge  TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_hack      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_beg       TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN farm_planted   TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN farm_amount    INTEGER DEFAULT 0;
    """,

    # Version 4 — rob cooldown
    """
    ALTER TABLE users ADD COLUMN last_rob TEXT DEFAULT NULL;
    """,

    # Version 5 — prestige, casino cooldowns, death count
    """
    ALTER TABLE users ADD COLUMN prestige        INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN last_blackjack  TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_gamble     TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN last_slots      TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN deaths          INTEGER DEFAULT 0;
    """,

    # Version 6 — loot items table
    """
    CREATE TABLE IF NOT EXISTS loot_items (
        loot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        description TEXT,
        sell_value  INTEGER NOT NULL,
        category    TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS loot_inventories (
        user_id  INTEGER NOT NULL,
        loot_id  INTEGER NOT NULL,
        quantity INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, loot_id)
    );
    """,

    # Version 7 — bank size limit + stock market
    """
    ALTER TABLE users ADD COLUMN bank_limit INTEGER DEFAULT 500;
    CREATE TABLE IF NOT EXISTS stocks (
        ticker       TEXT PRIMARY KEY,
        fake_name    TEXT NOT NULL,
        real_name    TEXT NOT NULL,
        price        REAL DEFAULT 0,
        prev_price   REAL DEFAULT 0,
        last_updated TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS stock_holdings (
        user_id  INTEGER NOT NULL,
        ticker   TEXT NOT NULL,
        shares   INTEGER DEFAULT 0,
        avg_cost REAL DEFAULT 0,
        PRIMARY KEY (user_id, ticker)
    );
    """,

    # Version 8 — passive income properties
    """
    CREATE TABLE IF NOT EXISTS user_properties (
        user_id        INTEGER NOT NULL,
        name           TEXT NOT NULL,
        purchased_at   TEXT DEFAULT (datetime('now')),
        last_collected TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, name)
    );
    """,

    # Version 9 — level system (xp already existed in v1, just ensure level column exists)
    """
    ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1;
    """,

    # Add future migrations below, never edit existing ones.
]


async def run_migrations(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        await db.commit()

        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row[0] is not None else 0

        for i, migration in enumerate(MIGRATIONS):
            version = i + 1
            if version <= current_version:
                continue

            logger.info(f"Applying migration v{version}...")
            try:
                for statement in migration.strip().split(";"):
                    s = statement.strip()
                    if s:
                        try:
                            await db.execute(s)
                        except Exception as e:
                            # Ignore "duplicate column" errors for ALTER TABLE
                            if "duplicate column" in str(e).lower():
                                pass
                            else:
                                raise
                await db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                await db.commit()
                logger.info(f"Migration v{version} done.")
            except Exception as e:
                logger.error(f"Migration v{version} failed: {e}")
                raise