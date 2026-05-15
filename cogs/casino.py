import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime

from utils.database import db
from utils.helpers import (
    economy_embed, error_embed, success_embed, info_embed,
    fmt_currency, register_command, apply_prestige
)

BET_MIN          = 10
CASINO_COOLDOWN  = 30   # seconds between casino uses

# ── Slots config ───────────────────────────────────────────────────────────────
# ── Slot machine — 6 symbols, 3 reels ────────────────────────────────────────
# ~62% win rate, ~93% return, house edge ~7%
# Win conditions:
#   3-of-a-kind: symbol-specific multiplier
#   2-of-a-kind (any two reels match, not all 3): 1.34x — returns bet + 34% profit
SLOT_SYMBOLS = ["💎", "⭐", "🍇", "🍊", "🍋", "🍒"]
SLOT_WEIGHTS = [5,    11,   19,   30,   48,   75]

SLOT_2OAK_MULT = 1.34  # any pair pays 1.34x

SLOT_3OAK_PAYOUTS = {
    "💎": 100,  # JACKPOT
    "⭐": 12,
    "🍇": 8,
    "🍊": 5,
    "🍋": 3,
    "🍒": 2,
}

SLOT_PAYTABLE = "💎x3=100x JACKPOT  |  ⭐x3=12x  |  🍇x3=8x  |  🍊x3=5x  |  🍋x3=3x  |  🍒x3=2x  |  Any pair=1.34x"

def spin_slots():
    return [random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0] for _ in range(3)]

def get_slot_result(reels):
    """
    Returns (multiplier, result_type).
    result_type: 'jackpot', '3oak', '2oak', 'loss'
    2oak triggers if any two reels match (but not all 3).
    """
    if reels[0] == reels[1] == reels[2]:
        mult = SLOT_3OAK_PAYOUTS[reels[0]]
        rtype = "jackpot" if reels[0] == "💎" else "3oak"
        return mult, rtype
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return SLOT_2OAK_MULT, "2oak"
    return 0, "loss"


async def check_bet(interaction, user, bet):
    if bet < BET_MIN:
        await interaction.response.send_message(
            embed=error_embed("Bet Too Low", f"Minimum bet is {fmt_currency(BET_MIN)}."), ephemeral=True
        )
        return False
    if bet > user["balance"]:
        short = bet - user["balance"]
        msg   = f"You don't have {fmt_currency(bet)} in your wallet."
        if user["bank"] >= short:
            msg += f"\nYou have enough in your bank — use `/withdraw` first."
        await interaction.response.send_message(embed=error_embed("Insufficient Wallet Funds", msg), ephemeral=True)
        return False
    return True


# ── Blackjack ──────────────────────────────────────────────────────────────────
CARD_VALUES = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10,"A":11}
SUITS       = ["♠","♥","♦","♣"]

def new_deck():
    return [(r, s) for r in CARD_VALUES for s in SUITS] * 2

def card_str(card):
    return f"{card[0]}{card[1]}"

def hand_value(hand):
    val  = sum(CARD_VALUES[c[0]] for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

def hand_str(hand):
    return " ".join(card_str(c) for c in hand)

def is_pair(hand):
    """Two cards with equal blackjack value."""
    return len(hand) == 2 and CARD_VALUES[hand[0][0]] == CARD_VALUES[hand[1][0]]

async def resolve_dealer(dealer, deck):
    """Dealer hits until 17+."""
    while hand_value(dealer) < 17:
        dealer.append(deck.pop())

async def settle_hand(interaction, player_hand, dealer, bet, prestige, log_suffix=""):
    """Compare a finished player hand against dealer. Returns result string."""
    pval = hand_value(player_hand)
    dval = hand_value(dealer)
    if pval > 21:
        await db.update_balance(interaction.user.id, -bet)
        await db.log_transaction(interaction.user.id, -bet, f"blackjack_loss{log_suffix}")
        return "lose", bet
    elif dval > 21 or pval > dval:
        winnings = apply_prestige(bet, prestige)
        await db.update_balance(interaction.user.id, winnings)
        await db.log_transaction(interaction.user.id, winnings, f"blackjack_win{log_suffix}")
        return "win", winnings
    elif pval == dval:
        return "push", 0
    else:
        await db.update_balance(interaction.user.id, -bet)
        await db.log_transaction(interaction.user.id, -bet, f"blackjack_loss{log_suffix}")
        return "lose", bet


class BlackjackView(discord.ui.View):
    """
    Handles a full blackjack hand including hit, stand, double, split, surrender.
    Split creates a second hand played sequentially.
    """
    def __init__(self, player_hand, dealer_hand, deck, bet, prestige, user_balance,
                 is_split_hand=False, split_hand=None, split_bet=None, split_is_aces=False):
        super().__init__(timeout=60)
        self.player       = player_hand
        self.dealer       = dealer_hand
        self.deck         = deck
        self.bet          = bet
        self.prestige     = prestige
        self.balance      = user_balance   # track available balance for double/split
        self.first_action = True           # surrender / double / split only on first action
        # Split state
        self.is_split_hand  = is_split_hand
        self.split_hand     = split_hand     # second hand after split (played after first)
        self.split_bet      = split_bet
        self.split_is_aces  = split_is_aces  # split aces only get one card each
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        pval = hand_value(self.player)
        # Always show Hit / Stand (unless split aces — no more actions)
        if not self.split_is_aces:
            self.add_item(self._hit_btn())
        self.add_item(self._stand_btn())
        # Double — only on first action if player can afford it
        if self.first_action and self.balance >= self.bet and not self.split_is_aces:
            self.add_item(self._double_btn())
        # Split — only on first action, only if it's a pair, player can afford it
        if (self.first_action and not self.is_split_hand
                and is_pair(self.player) and self.balance >= self.bet):
            self.add_item(self._split_btn())
        # Surrender — only on very first action (not after split)
        if self.first_action and not self.is_split_hand:
            self.add_item(self._surrender_btn())

    def _hit_btn(self):
        btn = discord.ui.Button(label="Hit", style=discord.ButtonStyle.primary)
        btn.callback = self._hit_callback
        return btn

    def _stand_btn(self):
        btn = discord.ui.Button(label="Stand", style=discord.ButtonStyle.secondary)
        btn.callback = self._stand_callback
        return btn

    def _double_btn(self):
        btn = discord.ui.Button(label=f"Double ({fmt_currency(self.bet * 2)})", style=discord.ButtonStyle.success)
        btn.callback = self._double_callback
        return btn

    def _split_btn(self):
        btn = discord.ui.Button(label=f"Split ({fmt_currency(self.bet * 2)} total)", style=discord.ButtonStyle.success)
        btn.callback = self._split_callback
        return btn

    def _surrender_btn(self):
        btn = discord.ui.Button(label="Surrender", style=discord.ButtonStyle.danger)
        btn.callback = self._surrender_callback
        return btn

    def build_embed(self, reveal=False, title="🃏 Blackjack", extra=""):
        pval = hand_value(self.player)
        dval = hand_value(self.dealer)
        dealer_display = hand_str(self.dealer) if reveal else f"{card_str(self.dealer[0])} 🂠"
        split_info = ""
        if self.split_hand is not None:
            split_info = f"\n**Waiting hand:** {hand_str(self.split_hand)} — **{hand_value(self.split_hand)}**"
        desc = (
            f"**Your hand:** {hand_str(self.player)} — **{pval}**{split_info}\n"
            f"**Dealer:** {dealer_display}{f' — **{dval}**' if reveal else ''}\n\n"
            f"**Bet:** {fmt_currency(self.bet)}{extra}"
        )
        embed = info_embed(title, desc)
        return embed

    async def _hit_callback(self, interaction: discord.Interaction):
        self.first_action = False
        self.player.append(self.deck.pop())
        pval = hand_value(self.player)
        if pval > 21:
            await self._end_hand(interaction, bust=True)
        elif pval == 21:
            # Auto-stand on 21
            await self._stand_callback(interaction)
        else:
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _stand_callback(self, interaction: discord.Interaction):
        if self.split_hand is not None:
            # First hand done — move to second hand
            await self._play_split_hand(interaction)
        else:
            await self._end_hand(interaction)

    async def _double_callback(self, interaction: discord.Interaction):
        self.bet *= 2
        self.first_action = False
        self.player.append(self.deck.pop())
        pval = hand_value(self.player)
        if pval > 21:
            await self._end_hand(interaction, bust=True)
        else:
            # After doubling, must stand
            await self._end_hand(interaction)

    async def _split_callback(self, interaction: discord.Interaction):
        # Split into two hands, deal one card to each
        card1 = self.player[0]
        card2 = self.player[1]
        self.player   = [card1, self.deck.pop()]
        self.split_hand = [card2, self.deck.pop()]
        self.split_bet  = self.bet
        self.split_is_aces = (card1[0] == "A")
        self.first_action  = False  # no surrender after split
        self._update_buttons()
        extra = f"\n**Waiting hand:** {hand_str(self.split_hand)} — **{hand_value(self.split_hand)}**"
        # Auto-stand split aces
        if self.split_is_aces:
            await self._play_split_hand(interaction)
        else:
            pval = hand_value(self.player)
            if pval == 21:
                await self._play_split_hand(interaction)
            else:
                embed = self.build_embed(extra=f"\n*Playing first hand — second hand waiting*")
                await interaction.response.edit_message(embed=embed, view=self)

    async def _surrender_callback(self, interaction: discord.Interaction):
        half = self.bet // 2
        # Return half the bet (player loses half)
        await db.update_balance(interaction.user.id, -(self.bet - half))
        await db.log_transaction(interaction.user.id, -(self.bet - half), "blackjack_surrender")
        self.stop()
        for child in self.children:
            child.disabled = True
        embed = self.build_embed(reveal=True, title=f"🏳️ Surrendered — lost {fmt_currency(self.bet - half)}")
        embed.color = 0x95A5A6
        await interaction.response.edit_message(embed=embed, view=self)

    async def _play_split_hand(self, interaction: discord.Interaction):
        """Move to playing the second split hand."""
        first_hand    = self.player
        first_bet     = self.bet
        second_hand   = self.split_hand
        second_bet    = self.split_bet
        dealer        = self.dealer
        deck          = self.deck
        prestige      = self.prestige

        # Dealer plays out now (both hands compare against same dealer result)
        await resolve_dealer(dealer, deck)
        dval = hand_value(dealer)

        # Settle first hand
        r1, amt1 = await settle_hand(interaction, first_hand, dealer, first_bet, prestige, "_split1")
        # Settle second hand
        r2, amt2 = await settle_hand(interaction, second_hand, dealer, second_bet, prestige, "_split2")

        def result_line(label, hand, result, amt):
            pval = hand_value(hand)
            if result == "win":
                return f"✅ **{label}:** {hand_str(hand)} ({pval}) — Win {fmt_currency(amt)}"
            elif result == "push":
                return f"⬜ **{label}:** {hand_str(hand)} ({pval}) — Push"
            else:
                return f"❌ **{label}:** {hand_str(hand)} ({pval}) — Lose {fmt_currency(amt)}"

        desc = (
            f"{result_line('Hand 1', first_hand, r1, amt1)}\n"
            f"{result_line('Hand 2', second_hand, r2, amt2)}\n\n"
            f"**Dealer:** {hand_str(dealer)} — **{dval}**"
        )
        embed = info_embed("🃏 Split Result", desc)
        embed.color = 0x2ECC71 if (r1 == "win" or r2 == "win") else 0xE74C3C
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    async def _end_hand(self, interaction: discord.Interaction, bust=False):
        await resolve_dealer(self.dealer, self.deck)
        result, amt = await settle_hand(interaction, self.player, self.dealer, self.bet, self.prestige)
        dval = hand_value(self.dealer)
        pval = hand_value(self.player)
        self.stop()
        for child in self.children:
            child.disabled = True
        if bust:
            embed = self.build_embed(reveal=True, title=f"💥 Bust! You lose {fmt_currency(self.bet)}.")
            embed.color = 0xE74C3C
        elif result == "win":
            embed = self.build_embed(reveal=True, title=f"✅ You win {fmt_currency(amt)}!")
            embed.color = 0x2ECC71
        elif result == "push":
            embed = self.build_embed(reveal=True, title="⬜ Push — bet returned.")
            embed.color = 0x95A5A6
        else:
            embed = self.build_embed(reveal=True, title=f"❌ Dealer wins. You lose {fmt_currency(self.bet)}.")
            embed.color = 0xE74C3C
        await interaction.response.edit_message(embed=embed, view=self)


# ── Cog ────────────────────────────────────────────────────────────────────────
class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /blackjack ─────────────────────────────────────────────────────────────
    @app_commands.command(name="blackjack", description="Play blackjack against the dealer.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Play blackjack with Hit, Stand, Double, Split, and Surrender.")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return

        deck   = new_deck()
        random.shuffle(deck)
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        prestige = user.get("prestige") or 0
        pval     = hand_value(player)
        dval     = hand_value(dealer)

        # Check dealer natural blackjack first
        dealer_natural = dval == 21

        # Natural blackjack for player
        if pval == 21:
            if dealer_natural:
                # Both have blackjack — push
                embed = info_embed("🃏 Push — Both Blackjack",
                    f"**Your hand:** {hand_str(player)} — **21**\n"
                    f"**Dealer:** {hand_str(dealer)} — **21**\n\nBoth have blackjack. Bet returned.")
                embed.color = 0x95A5A6
            else:
                winnings = apply_prestige(int(bet * 1.5), prestige)
                await db.update_balance(interaction.user.id, winnings)
                await db.log_transaction(interaction.user.id, winnings, "blackjack_natural")
                embed = info_embed("🃏 Blackjack! 🎉",
                    f"**Your hand:** {hand_str(player)} — **21**\n"
                    f"**Dealer:** {card_str(dealer[0])} 🂠\n\n"
                    f"Natural blackjack! You win {fmt_currency(winnings)}! (1.5x payout)")
                embed.color = 0xF1C40F
            return await interaction.response.send_message(embed=embed)

        # Dealer natural blackjack — player loses immediately (no actions)
        if dealer_natural:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "blackjack_loss_dealer_natural")
            embed = info_embed("🃏 Dealer Blackjack",
                f"**Your hand:** {hand_str(player)} — **{pval}**\n"
                f"**Dealer:** {hand_str(dealer)} — **21**\n\n"
                f"Dealer has blackjack. You lose {fmt_currency(bet)}.")
            embed.color = 0xE74C3C
            return await interaction.response.send_message(embed=embed)

        view = BlackjackView(player, dealer, deck, bet, prestige, user["balance"])
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    # ── /gamble ────────────────────────────────────────────────────────────────
    @app_commands.command(name="gamble", description="Roll a 12-sided dice against Vault. Higher roll wins.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Roll a 12-sided dice vs Vault. Higher roll wins your bet. Prestige boosts winnings.")
    async def gamble(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return

        prestige   = user.get("prestige") or 0
        your_roll  = random.randint(1, 12)
        vault_roll = random.randint(1, 12)

        if your_roll > vault_roll:
            winnings = apply_prestige(bet, prestige)
            await db.update_balance(interaction.user.id, winnings)
            await db.log_transaction(interaction.user.id, winnings, "gamble_win")
            embed = success_embed(
                f"You rolled {your_roll} — Vault rolled {vault_roll}",
                f"You win {fmt_currency(winnings)}!"
            )
        elif vault_roll > your_roll:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "gamble_loss")
            embed = error_embed(
                f"You rolled {your_roll} — Vault rolled {vault_roll}",
                f"Vault wins. You lose {fmt_currency(bet)}."
            )
        else:
            embed = info_embed(
                f"You rolled {your_roll} — Vault rolled {vault_roll}",
                "It's a tie! Your bet is returned."
            )

        await interaction.response.send_message(embed=embed)

    # ── /slots ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="slots", description="Spin the slot machine.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Spin the slots. Match symbols for multiplied payouts. Prestige boosts wins.")
    async def slots(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return

        prestige   = user.get("prestige") or 0
        reels      = spin_slots()
        multiplier, result_type = get_slot_result(reels)
        display    = " | ".join(reels)

        if result_type == "jackpot":
            winnings = int(apply_prestige(bet * multiplier, prestige))
            await db.update_balance(interaction.user.id, winnings)
            await db.log_transaction(interaction.user.id, winnings, "slots_jackpot")
            embed = discord.Embed(
                title=display,
                description=f"🌟 **JACKPOT! 710x!** 🌟\nYou win **{fmt_currency(winnings)}**!",
                color=0xFFD700
            )
        elif result_type == "3oak":
            winnings = int(apply_prestige(bet * multiplier, prestige))
            await db.update_balance(interaction.user.id, winnings)
            await db.log_transaction(interaction.user.id, winnings, "slots_win")
            embed = discord.Embed(
                title=display,
                description=f"**{multiplier}x!** You win {fmt_currency(winnings)}!",
                color=0xF1C40F
            )
        elif result_type == "2oak":
            winnings = int(apply_prestige(int(bet * SLOT_2OAK_MULT), prestige))
            await db.update_balance(interaction.user.id, winnings)
            await db.log_transaction(interaction.user.id, winnings, "slots_2oak")
            profit = winnings - bet
            embed = discord.Embed(
                title=display,
                description=f"**Pair! (+{fmt_currency(profit)} profit)** You win {fmt_currency(winnings)}!",
                color=0x3498DB
            )
        else:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "slots_loss")
            embed = discord.Embed(
                title=display,
                description=f"No match. You lose {fmt_currency(bet)}.",
                color=0xE74C3C
            )

        embed.set_footer(text=SLOT_PAYTABLE)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))