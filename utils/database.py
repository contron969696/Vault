import aiosqlite
import os
from utils.migrations import run_migrations

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/vault.db")

# ── Loot item definitions seeded on startup ────────────────────────────────────
LOOT_ITEMS = [
    # (name, description, sell_value, category)
    # Fishing
    ("Minnow",          "A tiny fish",                  15,    "fish"),
    ("Bass",            "A decent sized bass",          45,    "fish"),
    ("Catfish",         "A fat catfish",                100,   "fish"),
    ("Salmon",          "A fresh salmon",               220,   "fish"),
    ("Tuna",            "A massive tuna",               600,   "fish"),
    ("Golden Fish",     "A legendary golden fish",      2000,  "fish"),
    # Mining
    ("Coal",            "Common coal",                  25,    "ore"),
    ("Iron Ore",        "Rough iron ore",               55,    "ore"),
    ("Copper",          "Raw copper chunk",             110,   "ore"),
    ("Silver",          "A silver nugget",              240,   "ore"),
    ("Gold Nugget",     "A gold nugget",                550,   "ore"),
    ("Gemstone",        "A rare gemstone",              1800,  "ore"),
    # Hunting
    ("Rabbit Pelt",     "A small rabbit pelt",          30,    "pelt"),
    ("Turkey Feathers", "Wild turkey feathers",         70,    "pelt"),
    ("Deer Hide",       "A quality deer hide",          160,   "pelt"),
    ("Boar Tusk",       "A sharp boar tusk",            320,   "pelt"),
    ("Bear Fur",        "Thick black bear fur",         750,   "pelt"),
    ("Elk Antler",      "Rare white elk antler",        2200,  "pelt"),
    # Chopping
    ("Firewood",        "A bundle of firewood",         20,    "wood"),
    ("Oak Lumber",      "Planks of oak",                55,    "wood"),
    ("Pine Lumber",     "Planks of pine",               120,   "wood"),
    ("Honeycomb",       "Fresh honeycomb",              280,   "wood"),
    ("Chest",           "A hidden treasure chest",      700,   "wood"),
    ("Ancient Carving", "A valuable ancient piece",     2100,  "wood"),
    # Scavenging
    ("Phone Parts",     "Broken phone components",      12,    "junk"),
    ("Scrap Metal",     "Assorted scrap metal",         35,    "junk"),
    ("Old Microwave",   "A working microwave",          80,    "junk"),
    ("Loose Change",    "A bag of loose coins",         190,   "junk"),
    ("Vintage Item",    "A valuable vintage find",      430,   "junk"),
    ("Collector's Item","A rare collector's piece",     1200,  "junk"),
]


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def setup(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        await run_migrations(self.db_path)
        await self.seed_stocks()
        await self.seed_loot_items()

    # ── User ───────────────────────────────────────────────────────────────────
    async def ensure_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def get_user(self, user_id: int) -> dict | None:
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_balance(self, user_id: int, amount: int):
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?", (amount, user_id))
            await db.commit()

    async def update_bank(self, user_id: int, amount: int):
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET bank = MAX(0, bank + ?) WHERE user_id = ?", (amount, user_id))
            await db.commit()

    async def set_field(self, user_id: int, field: str, value):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
            await db.commit()

    async def set_job(self, user_id: int, job_name: str):
        await self.set_field(user_id, "job", job_name)

    async def wipe_wallet(self, user_id: int):
        """Called on death — clears wallet, increments death count."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET balance = 0, deaths = deaths + 1 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def prestige(self, user_id: int):
        """Increment prestige, wipe wallet, bank, job, and all inventories."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET
                    prestige = prestige + 1,
                    balance  = 0,
                    bank     = 0,
                    job      = 'Unemployed'
                WHERE user_id = ?
            """, (user_id,))
            await db.execute("DELETE FROM inventories WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM loot_inventories WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_leaderboard(self, limit: int = 10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_id, balance + bank AS total FROM users ORDER BY total DESC LIMIT ?", (limit,)
            ) as cursor:
                return [dict(row) async for row in cursor]

    async def log_transaction(self, user_id: int, amount: int, type: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)", (user_id, amount, type))
            await db.commit()

    async def reset_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM inventories WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM loot_inventories WHERE user_id = ?", (user_id,))
            await db.commit()

    # ── Tool Inventory ─────────────────────────────────────────────────────────
    async def has_item(self, user_id: int, item_name: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT i.quantity FROM inventories i
                JOIN shop_items s ON i.item_id = s.item_id
                WHERE i.user_id = ? AND LOWER(s.name) = LOWER(?)
            """, (user_id, item_name)) as cursor:
                row = await cursor.fetchone()
                return row is not None and row[0] > 0

    async def add_item(self, user_id: int, item_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO inventories (user_id, item_id, quantity) VALUES (?, ?, 1)
                ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + 1
            """, (user_id, item_id))
            await db.commit()

    async def remove_item(self, user_id: int, item_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE inventories SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?", (user_id, item_id))
            await db.execute("DELETE FROM inventories WHERE user_id = ? AND item_id = ? AND quantity <= 0", (user_id, item_id))
            await db.commit()

    async def get_inventory(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT s.name, s.description, s.price, i.quantity
                FROM inventories i JOIN shop_items s ON i.item_id = s.item_id
                WHERE i.user_id = ?
            """, (user_id,)) as cursor:
                return [dict(row) async for row in cursor]

    # ── Loot Inventory ─────────────────────────────────────────────────────────
    async def seed_loot_items(self):
        async with aiosqlite.connect(self.db_path) as db:
            for name, desc, sell, cat in LOOT_ITEMS:
                await db.execute("""
                    INSERT OR IGNORE INTO loot_items (name, description, sell_value, category)
                    VALUES (?, ?, ?, ?)
                """, (name, desc, sell, cat))
            await db.commit()

    async def get_loot_id(self, name: str) -> int | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT loot_id FROM loot_items WHERE name = ?", (name,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def add_loot(self, user_id: int, loot_name: str):
        loot_id = await self.get_loot_id(loot_name)
        if not loot_id:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO loot_inventories (user_id, loot_id, quantity) VALUES (?, ?, 1)
                ON CONFLICT(user_id, loot_id) DO UPDATE SET quantity = quantity + 1
            """, (user_id, loot_id))
            await db.commit()

    async def get_loot_inventory(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT l.name, l.description, l.sell_value, l.category, li.quantity
                FROM loot_inventories li JOIN loot_items l ON li.loot_id = l.loot_id
                WHERE li.user_id = ? AND li.quantity > 0
                ORDER BY l.category, l.sell_value
            """, (user_id,)) as cursor:
                return [dict(row) async for row in cursor]

    async def sell_loot(self, user_id: int, loot_name: str, quantity: int) -> tuple[bool, int]:
        """Returns (success, total_earned)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT li.quantity, l.sell_value, l.loot_id FROM loot_inventories li
                JOIN loot_items l ON li.loot_id = l.loot_id
                WHERE li.user_id = ? AND LOWER(l.name) = LOWER(?)
            """, (user_id, loot_name)) as cursor:
                row = await cursor.fetchone()
            if not row or row["quantity"] < quantity:
                return False, 0
            total = row["sell_value"] * quantity
            new_qty = row["quantity"] - quantity
            if new_qty <= 0:
                await db.execute("DELETE FROM loot_inventories WHERE user_id = ? AND loot_id = ?", (user_id, row["loot_id"]))
            else:
                await db.execute("UPDATE loot_inventories SET quantity = ? WHERE user_id = ? AND loot_id = ?", (new_qty, user_id, row["loot_id"]))
            await db.commit()
        await self.update_balance(user_id, total)
        return True, total

    async def get_loot_value(self, user_id: int) -> int:
        """Total sell value of all loot in inventory."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT SUM(l.sell_value * li.quantity)
                FROM loot_inventories li JOIN loot_items l ON li.loot_id = l.loot_id
                WHERE li.user_id = ? AND li.quantity > 0
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] or 0

    async def get_tool_value(self, user_id: int) -> int:
        """Total sell value (50%) of owned tools."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT SUM(s.price / 2 * i.quantity)
                FROM inventories i JOIN shop_items s ON i.item_id = s.item_id
                WHERE i.user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] or 0

    # ── Shop ───────────────────────────────────────────────────────────────────
    async def get_shop_items(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM shop_items ORDER BY price ASC") as cursor:
                return [dict(row) async for row in cursor]

    async def get_shop_item_by_name(self, name: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM shop_items WHERE LOWER(name) = LOWER(?)", (name,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def seed_shop(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM shop_items") as cursor:
                if (await cursor.fetchone())[0] > 0:
                    return
            items = [
                ("Fishing Rod",    "Required to use /fish",     2_000),
                ("Pickaxe",        "Required to use /mine",     5_000),
                ("Hunting Rifle",  "Required to use /hunt",    12_000),
                ("Axe",            "Required to use /chop",     8_000),
                ("Scavenger Bag",  "Required to use /scavenge", 3_500),
                ("Hacking Laptop", "Required to use /hack",    25_000),
                ("Tractor",        "Required to use /farm",    18_000),
            ]
            await db.executemany("INSERT INTO shop_items (name, description, price) VALUES (?, ?, ?)", items)
            await db.commit()


    # ── Bank Limit ─────────────────────────────────────────────────────────────
    async def grow_bank_limit(self, user_id: int, earned: int):
        """Increase bank limit by 25% of earnings."""
        increase = max(1, int(earned * 0.25))
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET bank_limit = bank_limit + ? WHERE user_id = ?",
                (increase, user_id)
            )
            await db.commit()

    async def update_bank_safe(self, user_id: int, amount: int) -> tuple[bool, int]:
        """
        Deposit to bank. Returns (success, space_available).
        Blocks if bank would exceed bank_limit.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT bank, bank_limit FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                return False, 0
            space = row["bank_limit"] - row["bank"]
            if amount > space:
                return False, space
            await db.execute(
                "UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id)
            )
            await db.commit()
            return True, space

    # ── Stocks ─────────────────────────────────────────────────────────────────
    async def seed_stocks(self):
        """Insert stock definitions if not present."""
        stocks = [
            ("AAPL",  "Apricot Inc.",         "Apple Inc."),
            ("MSFT",  "Microsoar Corp.",       "Microsoft"),
            ("NVDA",  "Nvidium Technologies",  "Nvidia"),
            ("AMZN",  "Amazonia Group",        "Amazon"),
            ("GOOGL", "Alphabeta Inc.",        "Alphabet"),
            ("META",  "Metaverse Co.",         "Meta"),
            ("BRK-B", "Birkwood Holdings",     "Berkshire Hathaway"),
            ("TSLA",  "Teslon Motors",         "Tesla"),
            ("AVGO",  "Broadwave Systems",     "Broadcom"),
            ("JPM",   "JPMorgue & Co.",        "JPMorgan"),
        ]
        async with aiosqlite.connect(self.db_path) as db:
            for ticker, fake, real in stocks:
                await db.execute(
                    "INSERT OR IGNORE INTO stocks (ticker, fake_name, real_name) VALUES (?, ?, ?)",
                    (ticker, fake, real)
                )
            await db.commit()

    async def update_stock_price(self, ticker: str, price: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE stocks SET prev_price = price, price = ?, last_updated = datetime('now')
                WHERE ticker = ?
            """, (price, ticker))
            await db.commit()

    async def get_all_stocks(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM stocks ORDER BY ticker") as cursor:
                return [dict(row) async for row in cursor]

    async def get_stock(self, ticker: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM stocks WHERE UPPER(ticker) = UPPER(?)", (ticker,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def buy_stock(self, user_id: int, ticker: str, shares: int, price: float) -> bool:
        """Buy shares. Returns False if insufficient wallet funds."""
        total_cost = int(shares * price)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or row["balance"] < total_cost:
                return False
            # Update wallet
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (total_cost, user_id)
            )
            # Upsert holding with updated avg cost
            async with db.execute(
                "SELECT shares, avg_cost FROM stock_holdings WHERE user_id = ? AND ticker = ?",
                (user_id, ticker)
            ) as cursor:
                holding = await cursor.fetchone()
            if holding:
                old_shares = holding["shares"]
                old_avg    = holding["avg_cost"]
                new_shares = old_shares + shares
                new_avg    = ((old_avg * old_shares) + (price * shares)) / new_shares
                await db.execute("""
                    UPDATE stock_holdings SET shares = ?, avg_cost = ?
                    WHERE user_id = ? AND ticker = ?
                """, (new_shares, new_avg, user_id, ticker))
            else:
                await db.execute("""
                    INSERT INTO stock_holdings (user_id, ticker, shares, avg_cost)
                    VALUES (?, ?, ?, ?)
                """, (user_id, ticker, shares, price))
            await db.commit()
            return True

    async def sell_stock(self, user_id: int, ticker: str, shares: int, price: float) -> tuple[bool, int]:
        """Sell shares. Returns (success, coins_received)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT shares FROM stock_holdings WHERE user_id = ? AND ticker = ?",
                (user_id, ticker)
            ) as cursor:
                holding = await cursor.fetchone()
            if not holding or holding["shares"] < shares:
                return False, 0
            proceeds = int(shares * price)
            new_shares = holding["shares"] - shares
            if new_shares == 0:
                await db.execute(
                    "DELETE FROM stock_holdings WHERE user_id = ? AND ticker = ?",
                    (user_id, ticker)
                )
            else:
                await db.execute(
                    "UPDATE stock_holdings SET shares = ? WHERE user_id = ? AND ticker = ?",
                    (new_shares, user_id, ticker)
                )
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (proceeds, user_id)
            )
            await db.commit()
            return True, proceeds

    async def get_portfolio(self, user_id: int) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT h.ticker, h.shares, h.avg_cost,
                       s.fake_name, s.price as current_price
                FROM stock_holdings h
                JOIN stocks s ON h.ticker = s.ticker
                WHERE h.user_id = ? AND h.shares > 0
                ORDER BY h.ticker
            """, (user_id,)) as cursor:
                return [dict(row) async for row in cursor]

    async def get_portfolio_value(self, user_id: int) -> int:
        rows = await self.get_portfolio(user_id)
        return int(sum(r["shares"] * r["current_price"] for r in rows))


db = Database()