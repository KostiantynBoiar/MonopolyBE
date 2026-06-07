# Frontend localization constants

These dicts mirror the canonical backend data so the frontend can render localized strings without the
backend shipping English prose. Keep in sync with `board_data.py` and `cards_data.py` if either
changes.

---

## Tiles

Board positions 0–39. Non-purchasable squares (corners, tax, chance, chest) are included so every
`tile_id` in a log entry can be resolved to a display name.

```js
const TILES = {
  "0":  "TYCOON",              // GO corner
  "1":  "Mediterranean Ave",
  "2":  "Community Chest",
  "3":  "Baltic Ave",
  "4":  "Income Tax",
  "5":  "Reading Railroad",
  "6":  "Oriental Ave",
  "7":  "Chance",
  "8":  "Vermont Ave",
  "9":  "Connecticut Ave",
  "10": "Just Visiting",       // Jail / visiting corner
  "11": "St. Charles Place",
  "12": "Electric Company",
  "13": "States Ave",
  "14": "Virginia Ave",
  "15": "Pennsylvania Railroad",
  "16": "St. James Place",
  "17": "Community Chest",
  "18": "Tennessee Ave",
  "19": "New York Ave",
  "20": "Free Parking",
  "21": "Kentucky Ave",
  "22": "Chance",
  "23": "Indiana Ave",
  "24": "Illinois Ave",
  "25": "B&O Railroad",
  "26": "Atlantic Ave",
  "27": "Ventnor Ave",
  "28": "Water Works",
  "29": "Marvin Gardens",
  "30": "Go to Jail",
  "31": "Pacific Ave",
  "32": "North Carolina Ave",
  "33": "Community Chest",
  "34": "Pennsylvania Ave",
  "35": "Short Line Railroad",
  "36": "Chance",
  "37": "Park Place",
  "38": "Luxury Tax",
  "39": "Boardwalk",
};
```

---

## Cards

### Chance (`card_kind: "chance"`)

```js
const CHANCE_CARDS = {
  "chance_01": "Advance to GO (Collect $200)",
  "chance_02": "Advance to Illinois Ave. If you pass GO, collect $200",
  "chance_03": "Advance to St. Charles Place. If you pass GO, collect $200",
  "chance_04": "Advance token to nearest Utility. If unowned, you may buy it.",
  "chance_05": "Advance token to nearest Railroad. Pay owner twice the rental.",
  "chance_06": "Advance token to nearest Railroad. Pay owner twice the rental.",
  "chance_07": "Bank pays you dividend of $50",
  "chance_08": "Get Out of Jail Free",
  "chance_09": "Go Back 3 Spaces",
  "chance_10": "Go to Jail. Go directly to Jail. Do not pass GO, do not collect $200",
  "chance_11": "Make general repairs on all your property — For each house pay $25 — For each hotel pay $100",
  "chance_12": "Speeding fine $15",
  "chance_13": "Take a trip to Reading Railroad. If you pass GO, collect $200",
  "chance_14": "Take a walk on the Boardwalk. Advance token to Boardwalk",
  "chance_15": "You have been elected Chairman of the Board. Pay each player $50",
  "chance_16": "Your building loan matures. Collect $150",
};
```

### Community Chest (`card_kind: "community_chest"`)

```js
const COMMUNITY_CHEST_CARDS = {
  "chest_01": "Advance to GO (Collect $200)",
  "chest_02": "Bank error in your favor. Collect $200",
  "chest_03": "Doctor's fees. Pay $50",
  "chest_04": "From sale of stock you get $50",
  "chest_05": "Get Out of Jail Free",
  "chest_06": "Go to Jail. Go directly to Jail. Do not pass GO, do not collect $200",
  "chest_07": "Holiday Fund matures. Collect $100",
  "chest_08": "Income tax refund. Collect $20",
  "chest_09": "It is your birthday. Collect $10 from every player",
  "chest_10": "Life insurance matures. Collect $100",
  "chest_11": "Pay hospital fees of $100",
  "chest_12": "Pay school fees of $150",
  "chest_13": "Receive $25 consultancy fee",
  "chest_14": "You are assessed for street repairs — $40 per house, $115 per hotel",
  "chest_15": "You have won second prize in a beauty contest. Collect $10",
  "chest_16": "You inherit $100",
};
```

---

## Event log `type` templates

Each `LogEntry` with `kind: "event"` carries a `type` and structured fields. Use these to build
localized display strings. Field names match the wire schema exactly.

| `type` | Suggested English template |
|--------|---------------------------|
| `player_moved` | `{player_name} rolled {rolled} and moved to {TILES[tile_id]}` (if `rolled` absent: `{player_name} moved to {TILES[tile_id]}`) |
| `passed_go` | `{player_name} passed GO and collected $${received}` |
| `rent_paid` | `{player_name} paid $${spent} rent on {TILES[tile_id]}` |
| `property_bought` | `{player_name} bought {TILES[tile_id]} for $${spent}` |
| `buy_declined` | `{player_name} declined to buy {TILES[tile_id]}` |
| `rolled_doubles` | `{player_name} rolled doubles ({streak} in a row)` |
| `sent_to_jail` | reason `doubles` → `{player_name} was sent to jail (three doubles in a row)` · reason `go_to_jail_space` → `{player_name} was sent to jail` · reason `card` → `{player_name} was sent to jail by a card` |
| `tax_paid` | `{player_name} paid $${spent} — {TILES[tile_id]}` |
| `turn_ended` | `It is now {player_name}'s turn` |
| `card_drawn` | `{player_name} drew a card: {CHANCE_CARDS[card_id]}` (or `COMMUNITY_CHEST_CARDS`) |
| `player_surrendered` | reason `voluntary` → `{player_name} surrendered` · reason `afk` → `{player_name} ran out of time and surrendered` |
| `turn_timed_out` | `{player_name} ran out of time (strike {strikes})` |
