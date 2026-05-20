import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.database import db
from utils.helpers import (
    economy_embed, error_embed, success_embed, info_embed,
    fmt_currency, register_command, apply_prestige
)
from utils.levels import grant_xp

BET_MIN = 10

SLOT_SYMBOLS = ["💎", "⭐", "🍇", "🍊", "🍋", "🍒"]
SLOT_WEIGHTS = [5, 11, 19, 30, 48, 75]
SLOT_2OAK_PROFIT = 0.34

SLOT_3OAK_PAYOUTS = {
    "💎": 100,
    "⭐": 12,
    "🍇": 8,
    "🍊": 5,
    "🍋": 3,
    "🍒": 2,
}

SLOT_PAYTABLE = "💎x3=100x JACKPOT | ⭐x3=12x | 🍇x3=8x | 🍊x3=5x | 🍋x3=3x | 🍒x3=2x | Any pair=1.34x"


def spin_slots():
    return [random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0] for _ in range(3)]


def get_slot_result(reels):
    if reels[0] == reels[1] == reels[2]:
        mult  = SLOT_3OAK_PAYOUTS[reels[0]]
        rtype = "jackpot" if reels[0] == "💎" else "3oak"
        return mult, rtype
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return SLOT_2OAK_PROFIT, "2oak"
    return 0, "loss"


async def check_bet(interaction, user, bet):
    if bet < BET_MIN:
        await interaction.response.send_message(
            embed=error_embed("Bet Too Low", f"Minimum bet is {fmt_currency(BET_MIN)}."), ephemeral=False
        )
        return False
    if bet > user["balance"]:
        short = bet - user["balance"]
        msg   = f"You don't have {fmt_currency(bet)} in your wallet."
        if user["bank"] >= short:
            msg += f"\nYou have enough in your bank — use `/withdraw` first."
        await interaction.response.send_message(embed=error_embed("Insufficient Wallet Funds", msg), ephemeral=False)
        return False
    return True


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


# ── Blackjack ──────────────────────────────────────────────────────────────────

CARD_VALUES = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10,"A":11}
SUITS = ["♠","♥","♦","♣"]


def new_deck():
    return [(r, s) for r in CARD_VALUES for s in SUITS] * 2

def card_str(card):   return f"{card[0]}{card[1]}"
def hand_str(hand):   return " ".join(card_str(c) for c in hand)
def is_pair(hand):    return len(hand) == 2 and CARD_VALUES[hand[0][0]] == CARD_VALUES[hand[1][0]]

def hand_value(hand):
    val  = sum(CARD_VALUES[c[0]] for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while val > 21 and aces:
        val -= 10; aces -= 1
    return val

async def resolve_dealer(dealer, deck):
    while hand_value(dealer) < 17:
        dealer.append(deck.pop())

async def settle_hand(interaction, player_hand, dealer, bet, log_suffix=""):
    """Compare a finished player hand against dealer. No prestige multiplier on casino wins."""
    pval = hand_value(player_hand)
    dval = hand_value(dealer)
    if pval > 21:
        await db.update_balance(interaction.user.id, -bet)
        await db.log_transaction(interaction.user.id, -bet, f"blackjack_loss{log_suffix}")
        return "lose", bet
    elif dval > 21 or pval > dval:
        await db.update_balance(interaction.user.id, bet)
        await db.log_transaction(interaction.user.id, bet, f"blackjack_win{log_suffix}")
        return "win", bet
    elif pval == dval:
        return "push", 0
    else:
        await db.update_balance(interaction.user.id, -bet)
        await db.log_transaction(interaction.user.id, -bet, f"blackjack_loss{log_suffix}")
        return "lose", bet


class BlackjackView(discord.ui.View):

    def __init__(self, player_hand, dealer_hand, deck, bet, user_balance,
                 is_split_hand=False, split_hand=None, split_bet=None, split_is_aces=False):
        super().__init__(timeout=60)
        self.player       = player_hand
        self.dealer       = dealer_hand
        self.deck         = deck
        self.bet          = bet
        self.balance      = user_balance
        self.first_action = True
        self.is_split_hand  = is_split_hand
        self.split_hand     = split_hand
        self.split_bet      = split_bet
        self.split_is_aces  = split_is_aces
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        if not self.split_is_aces:
            self.add_item(self._btn("Hit",       discord.ButtonStyle.primary,   self._hit_callback))
            self.add_item(self._btn("Stand",     discord.ButtonStyle.secondary, self._stand_callback))
        if self.first_action and self.balance >= self.bet and not self.split_is_aces:
            self.add_item(self._btn(f"Double ({fmt_currency(self.bet*2)})", discord.ButtonStyle.success, self._double_callback))
        if self.first_action and not self.is_split_hand and is_pair(self.player) and self.balance >= self.bet:
            self.add_item(self._btn(f"Split ({fmt_currency(self.bet*2)} total)", discord.ButtonStyle.success, self._split_callback))
        if self.first_action and not self.is_split_hand:
            self.add_item(self._btn("Surrender", discord.ButtonStyle.danger, self._surrender_callback))

    def _btn(self, label, style, callback):
        btn = discord.ui.Button(label=label, style=style)
        btn.callback = callback
        return btn

    def build_embed(self, reveal=False, title="🃏 Blackjack", extra=""):
        pval           = hand_value(self.player)
        dval           = hand_value(self.dealer)
        dealer_display = hand_str(self.dealer) if reveal else f"{card_str(self.dealer[0])} 🂠"
        split_info     = f"\n**Waiting hand:** {hand_str(self.split_hand)} — **{hand_value(self.split_hand)}**" if self.split_hand else ""
        desc = (
            f"**Your hand:** {hand_str(self.player)} — **{pval}**{split_info}\n"
            f"**Dealer:** {dealer_display}{f' — **{dval}**' if reveal else ''}\n\n"
            f"**Bet:** {fmt_currency(self.bet)}{extra}"
        )
        return info_embed(title, desc)

    async def _hit_callback(self, interaction):
        self.first_action = False
        self.player.append(self.deck.pop())
        pval = hand_value(self.player)
        if pval > 21:    await self._end_hand(interaction, bust=True)
        elif pval == 21: await self._stand_callback(interaction)
        else:
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _stand_callback(self, interaction):
        if self.split_hand is not None: await self._play_split_hand(interaction)
        else:                           await self._end_hand(interaction)

    async def _double_callback(self, interaction):
        # Verify player can actually afford the extra bet
        user = await db.get_user(interaction.user.id)
        if user["balance"] < self.bet:
            await interaction.response.send_message(
                embed=error_embed("Insufficient Funds",
                    f"You need {fmt_currency(self.bet)} in your wallet to double down."),
                ephemeral=False
            )
            return
        self.balance -= self.bet  # update tracked balance
        self.bet *= 2
        self.first_action = False
        self.player.append(self.deck.pop())
        if hand_value(self.player) > 21: await self._end_hand(interaction, bust=True)
        else:                            await self._end_hand(interaction)

    async def _split_callback(self, interaction):
        # Verify player can actually afford the split
        user = await db.get_user(interaction.user.id)
        if user["balance"] < self.bet:
            await interaction.response.send_message(
                embed=error_embed("Insufficient Funds",
                    f"You need {fmt_currency(self.bet)} in your wallet to split."),
                ephemeral=False
            )
            return
        self.balance -= self.bet  # update tracked balance
        c1, c2          = self.player[0], self.player[1]
        self.player     = [c1, self.deck.pop()]
        self.split_hand = [c2, self.deck.pop()]
        self.split_bet  = self.bet
        self.split_is_aces = (c1[0] == "A")
        self.first_action  = False
        self._update_buttons()
        if self.split_is_aces or hand_value(self.player) == 21:
            await self._play_split_hand(interaction)
        else:
            await interaction.response.edit_message(
                embed=self.build_embed(extra="\n*Playing first hand — second hand waiting*"), view=self)

    async def _surrender_callback(self, interaction):
        half = self.bet // 2
        await db.update_balance(interaction.user.id, -(self.bet - half))
        await db.log_transaction(interaction.user.id, -(self.bet - half), "blackjack_surrender")
        self.stop()
        for c in self.children: c.disabled = True
        embed = self.build_embed(reveal=True, title=f"🏳️ Surrendered — lost {fmt_currency(self.bet - half)}")
        embed.color = 0x95A5A6
        await interaction.response.edit_message(embed=embed, view=self)

    async def _play_split_hand(self, interaction):
        await resolve_dealer(self.dealer, self.deck)
        dval     = hand_value(self.dealer)
        r1, amt1 = await settle_hand(interaction, self.player,     self.dealer, self.bet,       "_split1")
        r2, amt2 = await settle_hand(interaction, self.split_hand, self.dealer, self.split_bet, "_split2")

        def line(label, hand, result, amt):
            pval = hand_value(hand)
            if result == "win":    return f"✅ **{label}:** {hand_str(hand)} ({pval}) — Win {fmt_currency(amt)}"
            elif result == "push": return f"⬜ **{label}:** {hand_str(hand)} ({pval}) — Push"
            else:                  return f"❌ **{label}:** {hand_str(hand)} ({pval}) — Lose {fmt_currency(amt)}"

        embed = info_embed("🃏 Split Result",
            f"{line('Hand 1',self.player,r1,amt1)}\n{line('Hand 2',self.split_hand,r2,amt2)}\n\n"
            f"**Dealer:** {hand_str(self.dealer)} — **{dval}**")
        embed.color = 0x2ECC71 if (r1=="win" or r2=="win") else 0xE74C3C
        self.stop()
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        if r1 == "win" or r2 == "win":
            total_win = (amt1 if r1=="win" else 0) + (amt2 if r2=="win" else 0)
            xp = 25 + (total_win // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await maybe_levelup(interaction, leveled_up, new_level)

    async def _end_hand(self, interaction, bust=False):
        await resolve_dealer(self.dealer, self.deck)
        result, amt = await settle_hand(interaction, self.player, self.dealer, self.bet)
        self.stop()
        for c in self.children: c.disabled = True
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
        if result == "win":
            xp = 25 + (amt // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await maybe_levelup(interaction, leveled_up, new_level)


# ── Cog ────────────────────────────────────────────────────────────────────────

class Casino(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Play blackjack against the dealer.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Play blackjack with Hit, Stand, Double, Split, and Surrender.")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return
        deck   = new_deck(); random.shuffle(deck)
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        pval           = hand_value(player)
        dval           = hand_value(dealer)
        dealer_natural = dval == 21

        if pval == 21:
            if dealer_natural:
                embed = info_embed("🃏 Push — Both Blackjack",
                    f"**Your hand:** {hand_str(player)} — **21**\n**Dealer:** {hand_str(dealer)} — **21**\n\nBoth have blackjack. Bet returned.")
                embed.color = 0x95A5A6
            else:
                winnings = int(bet * 1.5)
                await db.update_balance(interaction.user.id, winnings)
                await db.log_transaction(interaction.user.id, winnings, "blackjack_natural")
                xp = 25 + (winnings // 100)
                leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
                embed = info_embed("🃏 Blackjack! 🎉",
                    f"**Your hand:** {hand_str(player)} — **21**\n**Dealer:** {card_str(dealer[0])} 🂠\n\n"
                    f"Natural blackjack! You win {fmt_currency(winnings)}! (1.5x payout)\n+{xp} XP")
                embed.color = 0xF1C40F
                await interaction.response.send_message(embed=embed)
                await maybe_levelup(interaction, leveled_up, new_level)
                return
            return await interaction.response.send_message(embed=embed)

        if dealer_natural:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "blackjack_loss_dealer_natural")
            embed = info_embed("🃏 Dealer Blackjack",
                f"**Your hand:** {hand_str(player)} — **{pval}**\n**Dealer:** {hand_str(dealer)} — **21**\n\n"
                f"Dealer has blackjack. You lose {fmt_currency(bet)}.")
            embed.color = 0xE74C3C
            return await interaction.response.send_message(embed=embed)

        view = BlackjackView(player, dealer, deck, bet, user["balance"])
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    @app_commands.command(name="gamble", description="Roll a 12-sided dice against Vault. Higher roll wins.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Roll a 12-sided dice vs Vault. Higher roll wins your bet.")
    async def gamble(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return
        your_roll  = random.randint(1, 12)
        vault_roll = random.randint(1, 12)
        if your_roll > vault_roll:
            # No prestige multiplier on gambling
            await db.update_balance(interaction.user.id, bet)
            await db.log_transaction(interaction.user.id, bet, "gamble_win")
            xp = 25 + (bet // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            await interaction.response.send_message(
                embed=success_embed(f"You rolled {your_roll} — Vault rolled {vault_roll}",
                    f"You win {fmt_currency(bet)}!\n+{xp} XP")
            )
            await maybe_levelup(interaction, leveled_up, new_level)
        elif vault_roll > your_roll:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "gamble_loss")
            await interaction.response.send_message(
                embed=error_embed(f"You rolled {your_roll} — Vault rolled {vault_roll}",
                    f"Vault wins. You lose {fmt_currency(bet)}.")
            )
        else:
            await interaction.response.send_message(
                embed=info_embed(f"You rolled {your_roll} — Vault rolled {vault_roll}",
                    "It's a tie! Your bet is returned.")
            )

    @app_commands.command(name="slots", description="Spin the slot machine.")
    @app_commands.describe(bet="How much to bet (min 10, from wallet)")
    @register_command("Casino", "Spin the slots. Match symbols for multiplied payouts.")
    async def slots(self, interaction: discord.Interaction, bet: int):
        user = await db.get_user(interaction.user.id)
        if not await check_bet(interaction, user, bet):
            return
        reels                   = spin_slots()
        multiplier, result_type = get_slot_result(reels)
        display                 = " | ".join(reels)

        if result_type == "jackpot":
            # No prestige multiplier on gambling
            profit = int(bet * (multiplier - 1))
            await db.update_balance(interaction.user.id, profit)
            await db.log_transaction(interaction.user.id, profit, "slots_jackpot")
            xp = 25 + (profit // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            embed = discord.Embed(title=display,
                description=f"🌟 **JACKPOT! {multiplier}x!** 🌟\nYou win **{fmt_currency(profit)}**!\n+{xp} XP",
                color=0xFFD700)
            embed.set_footer(text=SLOT_PAYTABLE)
            await interaction.response.send_message(embed=embed)
            await maybe_levelup(interaction, leveled_up, new_level)

        elif result_type == "3oak":
            profit = int(bet * (multiplier - 1))
            await db.update_balance(interaction.user.id, profit)
            await db.log_transaction(interaction.user.id, profit, "slots_win")
            xp = 25 + (profit // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            embed = discord.Embed(title=display,
                description=f"**{multiplier}x!** You win {fmt_currency(profit)}!\n+{xp} XP",
                color=0xF1C40F)
            embed.set_footer(text=SLOT_PAYTABLE)
            await interaction.response.send_message(embed=embed)
            await maybe_levelup(interaction, leveled_up, new_level)

        elif result_type == "2oak":
            profit = int(bet * multiplier)
            await db.update_balance(interaction.user.id, profit)
            await db.log_transaction(interaction.user.id, profit, "slots_2oak")
            xp = 25 + (profit // 100)
            leveled_up, _, new_level = await grant_xp(interaction.user.id, xp)
            embed = discord.Embed(title=display,
                description=f"**Pair! (+{fmt_currency(profit)} profit)**\n+{xp} XP",
                color=0x3498DB)
            embed.set_footer(text=SLOT_PAYTABLE)
            await interaction.response.send_message(embed=embed)
            await maybe_levelup(interaction, leveled_up, new_level)

        else:
            await db.update_balance(interaction.user.id, -bet)
            await db.log_transaction(interaction.user.id, -bet, "slots_loss")
            embed = discord.Embed(title=display,
                description=f"No match. You lose {fmt_currency(bet)}.",
                color=0xE74C3C)
            embed.set_footer(text=SLOT_PAYTABLE)
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Casino(bot))