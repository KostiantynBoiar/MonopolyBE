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

---

## Expected JSON shapes from the backend

All responses are `snake_case`. Null-valued optional fields are omitted by Pydantic's `model_dump`.
The examples below show only the non-null fields that appear for each case.

### `active_card` (inside `game.state` payload)

Appears briefly after a player draws a Chance or Community Chest card; clears on the next command.
Effect is a discriminated union on `effect.type` — all variants shown below.

```jsonc
// advance_to
{
  "id": "chance_01",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "advance_to", "position": 0, "collect_go_bonus": true }
}

// advance_to_nearest
{
  "id": "chance_05",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "advance_to_nearest", "space_type": "railroad", "pay_double": true }
}

// go_to_jail
{
  "id": "chance_10",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "go_to_jail" }
}

// go_back
{
  "id": "chance_09",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "go_back", "spaces": 3 }
}

// collect
{
  "id": "chest_02",
  "kind": "community_chest",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "collect", "amount": 200 }
}

// pay
{
  "id": "chest_03",
  "kind": "community_chest",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "pay", "amount": 50 }
}

// collect_from_each_player
{
  "id": "chest_09",
  "kind": "community_chest",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "collect_from_each_player", "amount": 10 }
}

// pay_each_player
{
  "id": "chance_15",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "pay_each_player", "amount": 50 }
}

// get_out_of_jail_free
{
  "id": "chance_08",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "get_out_of_jail_free" }
}

// repairs
{
  "id": "chance_11",
  "kind": "chance",
  "drawer_id": "2d557bc42a06463b90ec74fc95715332",
  "effect": { "type": "repairs", "per_house": 25, "per_hotel": 100 }
}
```

---

### `log[]` entries (inside `game.state` payload)

Every game-event entry has `"kind": "event"`. Only fields relevant to that `type` are present;
all other optional fields are omitted. `player_name` and `player_token` are convenience fallbacks —
prefer resolving from `player_id` against the `players` array when possible.

```jsonc
// player_moved — dice roll (rolled present)
{
  "id": "6a1addb5fa3443a0b434bcb1a1625fea",
  "kind": "event",
  "ts": "2026-06-07T21:57:25.092746Z",
  "type": "player_moved",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "player_token": "blue",
  "tile_id": 7,
  "rolled": 7
}

// player_moved — card / teleport / jail (rolled absent)
{
  "id": "a3f1cc84b2e041e0b8d09fa3c7261900",
  "kind": "event",
  "ts": "2026-06-07T21:57:30.000000Z",
  "type": "player_moved",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "player_token": "blue",
  "tile_id": 39
}

// passed_go
{
  "id": "b9e2a14f88cd4d1089c3f2e710a83b22",
  "kind": "event",
  "ts": "2026-06-07T21:57:25.100000Z",
  "type": "passed_go",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "received": 200
}

// rent_paid
{
  "id": "fe33d963006648f7acae40b0e8d69ae8",
  "kind": "event",
  "ts": "2026-06-07T21:58:48.970282Z",
  "type": "rent_paid",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "opponent_id": "9b84c1a0334e4f2da1c6e5b738f920d1",
  "tile_id": 15,
  "spent": 100
}

// property_bought
{
  "id": "c01a23de456f789b012c34d5e678f901",
  "kind": "event",
  "ts": "2026-06-07T21:58:48.970282Z",
  "type": "property_bought",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "tile_id": 15,
  "spent": 200
}

// buy_declined
{
  "id": "d12b34cd567e890a123d45e6f789a012",
  "kind": "event",
  "ts": "2026-06-07T21:59:00.000000Z",
  "type": "buy_declined",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "tile_id": 15
}

// rolled_doubles
{
  "id": "e23c45de678f901b234e56f7a890b123",
  "kind": "event",
  "ts": "2026-06-07T22:00:00.000000Z",
  "type": "rolled_doubles",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "streak": 2
}

// sent_to_jail — reason codes: "doubles" | "go_to_jail_space" | "card"
{
  "id": "f34d56ef789a012c345f67a8b901c234",
  "kind": "event",
  "ts": "2026-06-07T22:00:05.000000Z",
  "type": "sent_to_jail",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "reason": "doubles"
}

// tax_paid (tile_id 4 = Income Tax, 38 = Luxury Tax)
{
  "id": "045e67f0890b123d456a78b9c012d345",
  "kind": "event",
  "ts": "2026-06-07T22:01:00.000000Z",
  "type": "tax_paid",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "tile_id": 4,
  "spent": 200
}

// turn_ended — player_id is the NEXT player (whose turn it now is)
{
  "id": "156f78a0901c234e567b89c0d123e456",
  "kind": "event",
  "ts": "2026-06-07T22:02:00.000000Z",
  "type": "turn_ended",
  "player_id": "9b84c1a0334e4f2da1c6e5b738f920d1",
  "player_name": "Bob"
}

// card_drawn
{
  "id": "267a89b0012d345f678c90d1e234f567",
  "kind": "event",
  "ts": "2026-06-07T22:03:00.000000Z",
  "type": "card_drawn",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "card_id": "chance_06",
  "card_kind": "chance"
}

// player_surrendered — reason: "voluntary" | "afk"
{
  "id": "378b90c0123e456a789d01e2f345a678",
  "kind": "event",
  "ts": "2026-06-07T22:04:00.000000Z",
  "type": "player_surrendered",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "reason": "afk"
}

// turn_timed_out
{
  "id": "489c01d0234f567b890e12f3a456b789",
  "kind": "event",
  "ts": "2026-06-07T22:05:00.000000Z",
  "type": "turn_timed_out",
  "player_id": "2d557bc42a06463b90ec74fc95715332",
  "player_name": "Alice",
  "strikes": 2
}
```
