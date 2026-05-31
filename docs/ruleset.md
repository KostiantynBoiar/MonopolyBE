# Monopoly Ruleset — Canonical Reference

Authoritative spec for the backend game engine. Rule modules in `src/domain/game/rules/`
implement sections below.

## Constants

| Rule | Value |
|------|-------|
| Starting balance | $1,500 |
| Pass GO salary | $200 |
| Jail fine / bail | $50 |
| Bank houses | 32 |
| Bank hotels | 12 |
| Mortgage interest | 10% (unmortgage = ceil(mortgage_value × 1.1)) |
| House sell credit | 50% of house cost |
| Railroad rent | $25 / $50 / $100 / $200 (1–4 owned) |
| Utility rent | ×4 dice (1 owned) / ×10 dice (2 owned) |
| Income tax | $200 |
| Luxury tax | $100 |
| Free Parking | No payout (no money pot) |
| Doubles | Extra roll; 3rd consecutive double → jail |
| Win condition | Last non-bankrupt player |

## Cross-cutting invariants (after every command)

1. **Bank inventory:** `bank_houses` / `bank_hotels` on game state; block building when unavailable.
2. **Even build/sell:** build only on group-minimum tile; sell only on group-maximum tile.
3. **Mortgage gating:** no mortgage if tile or group-mate has buildings; mortgaged tiles collect no rent; building blocked if any group-mate mortgaged.
4. **Win check:** exactly one non-bankrupt player → `status=finished`, `winner_id`, `phase=game_over`.

## Cards (Chance & Community Chest)

- 16 Chance + 16 Community Chest cards (standard US edition).
- Auto-apply on draw; no client card intent.
- Normal cards cycle to back of deck; Get Out of Jail Free removed on draw, returned on use.
- Movement cards re-run landing resolution (recursion cap 3 for go-back → Chest chains).

### Card effect types

- `advance_to` — move to position; optional GO salary if passing GO
- `advance_to_nearest` — nearest railroad or utility; optional double rent
- `go_to_jail` — send to jail; no GO salary; POST_ROLL, no extra roll
- `go_back` — move back N spaces; re-resolve landing
- `collect` / `pay` — fixed amount
- `collect_from_each_player` / `pay_each_player` — per-opponent amounts
- `get_out_of_jail_free` — add to player's card count
- `repairs` — per house / per hotel on owned properties

## Jail

- Jailed player starts turn in `jail_decision`: roll, pay $50 fine, or use Get Out of Jail Free card.
- Roll in jail: doubles → leave and move (no bonus roll); non-doubles → `turns_remaining -= 1`.
- Third failed roll → auto-pay bail and move.
- Pay fine / use card → released to `pre_roll` (may roll normally).
- End turn routes next jailed player to `jail_decision`.
- Any outcome sending player to jail forces `post_roll` and resets doubles streak.

## Building

- Requires full unmortgaged color group (monopoly).
- Even build: add house only on tile with minimum houses in group.
- Even sell: remove house only from tile with maximum houses in group.
- 5th house → hotel (houses → 0, `has_hotel=true`, 4 houses return to bank, 1 hotel from bank).
- Sell house credits 50% of house cost.
- Block when bank has no houses/hotels (housing-shortage auction deferred to auction milestone).

## Mortgage

- Mortgage credits `mortgage_value`; unmortgage costs `ceil(mortgage_value × 1.1)`.
- Cannot mortgage if tile or any group-mate has buildings.
- Mortgaged properties collect no rent.

## Trading

- Trade money, properties (incl. mortgaged), and Get Out of Jail Free cards.
- Houses/hotels not tradable; sell buildings before trading a property.
- Accept → atomic asset swap.

## Auctions

- Declining to buy unowned property triggers auction among solvent players.
- Highest bidder wins at bid price; no bids → property stays with bank.
- Timers handled by application-layer scheduler (`AdvanceAuction` system command).

## Bankruptcy

- Debt exceeds cash → `bankrupt_resolution`; player may sell/mortgage first.
- **To player:** transfer cash, properties, GOOJF; creditor pays 10% on received mortgaged properties.
- **To bank:** return GOOJF to deck; auction all properties.
- `is_bankrupt=true`; single survivor wins.
