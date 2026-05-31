# Game Protocol (in-game play)

FE-facing contract for the **in-game** phase: how a game starts, the `game.state` snapshot every
client renders, and every `game.*` intent a client can send. The lobby/session + chat layer (auth,
WebSocket connection, `session.updated`, chat) is documented in
[`sessions-and-realtime.md`](./sessions-and-realtime.md); this doc assumes you've already connected to
`/ws/sessions/{session_id}` with the `bearer,<jwt>` subprotocol.

**Wire format is `snake_case`** (REST + WS). Transform to camelCase at the FE boundary if you prefer.

---

## 1. The full flow

```
REST  POST /api/v1/auth/register|login            → { user, token }
REST  POST /api/v1/sessions                        → create a session (host)
REST  POST /api/v1/sessions/{id}/join              → guests join
WS    connect /ws/sessions/{id}  (bearer subproto) → system.welcome  (+ game.state if already started)
REST  POST /api/v1/sessions/{id}/start  (host)     → server creates the game
                                                     → broadcast: session.updated, then game.state
WS    send  game.roll_dice / game.buy_property ...  → server validates + broadcasts a new game.state
...   play until one player remains                 → game.state.status = "finished" + winner_id
                                                     → session flips to "finished" (session.updated)
```

- **Starting a game:** only the host calls `POST /api/v1/sessions/{id}/start`. The server builds the
  game (random seeded turn order, $1500 each) and broadcasts the opening `game.state` to all members.
- **On (re)connect:** after `system.welcome` the server immediately sends the current `game.state` (if a
  game exists) to the joining socket, so reconnects resync automatically.
- **Every move:** send one `game.*` intent; the server applies it authoritatively and broadcasts the
  resulting `game.state` to **all** members (each gets their own per-viewer frame — see §3).

---

## 2. Message envelope

All WS frames share the envelope from the session protocol:

```json
{ "v": 1, "type": "<type>", "ts": "<ISO8601>", "seq": 42, "idempotency_key": null, "payload": { } }
```

- `seq` — monotonic per session, present on server→client broadcasts. All recipients of one state
  change get the **same** `seq` (even though their `payload` differs per-viewer).
- Inbound (client→server) frames omit `seq`.

### Inbound game types (client → server)
| `type` | `payload` |
|--------|-----------|
| `game.roll_dice` | `{}` |
| `game.buy_property` | `{ "position": 0–39 }` |
| `game.pass_buy` | `{}` |
| `game.end_turn` | `{}` |
| `game.pay_jail_fine` | `{}` |
| `game.use_jail_card` | `{}` |
| `game.build_house` | `{ "position": 0–39 }` |
| `game.sell_house` | `{ "position": 0–39 }` |
| `game.mortgage` | `{ "position": 0–39 }` |
| `game.unmortgage` | `{ "position": 0–39 }` |
| `game.propose_trade` | `{ "target_id", "proposer_offer": TradeOffer, "target_request": TradeOffer }` |
| `game.respond_trade` | `{ "trade_id", "response": "accept"\|"reject"\|"counter", "counter_offer"?: TradeOffer }` |
| `game.place_bid` | `{ "amount": >0 }` |
| `game.declare_bankruptcy` | `{}` |

`TradeOffer` = `{ "money": int≥0, "positions": int[], "get_out_of_jail_cards": int≥0 }`.

### Outbound game types (server → client)
| `type` | `payload` |
|--------|-----------|
| `game.state` | the full snapshot (§3) — **per-viewer** |
| `system.error` | `{ "code", "message", "ref_seq"? }` — see §6 |
| `system.welcome`, `connection.ping`, `chat.message`, `chat.sticker`, `session.updated` | see `sessions-and-realtime.md` |

---

## 3. `game.state` — the snapshot

The server broadcasts a `game.state` after every applied command. **It is rendered per recipient:**
`viewer_id` and `turn.actions_available` are scoped to *that* connection's player. Two players receive
the same `seq` but different `viewer_id`/`actions_available`.

> **Not sent to clients:** the card deck order (`chance_deck`/`chest_deck`) is server-only and stripped
> from every client frame. Don't expect it.

```jsonc
{
  "v": 1, "type": "game.state", "ts": "...", "seq": 12,
  "payload": {
    "game_id": "…",
    "session_code": "TYC-A1B2",
    "status": "in_progress",          // "in_progress" | "finished"
    "created_at": "…", "started_at": "…", "finished_at": null,
    "winner_id": null,                // player id once finished

    "viewer_id": "<your player id>",  // ← who *you* are (per-recipient)

    "players": [ PlayerState, … ],    // ordered by turn_order
    "turn": TurnState,
    "spaces": [ SpaceOwnership × 40 ],

    "auction": AuctionState | null,   // at most one of these three/four is non-null
    "trade": TradeState | null,
    "active_card": ActiveCard | null,
    "bankruptcy": BankruptcyState | null,

    "bank_houses": 32,                // remaining building inventory (public)
    "bank_hotels": 12,

    "log": [ LogEntry, … ]            // append-only events (kind:"event"); chat arrives separately
  }
}
```

### PlayerState
`id`, `user_id`, `display_name`, `token` (one of `blue red green yellow orange pink cyan brown gold ink`),
`avatar_url` (str|null), `turn_order` (int), `position` (0–39), `balance` (int),
`owned_positions` (int[]), `get_out_of_jail_cards` (int), `jail_status` (`{ "turns_remaining": int }` |
null), `is_bankrupt` (bool), `is_connected` (bool), `net_worth` (int, server-computed).

### TurnState
`phase` (see §4), `current_player_id`, `turn_number`, `round_number`,
`dice_roll` (`{ "die1":1–6, "die2":1–6, "is_doubles":bool }` | null),
`doubles_streak` (0–2), `pending_buy_position` (int|null — the tile awaiting buy/pass),
`actions_available` (ActionSet).

### ActionSet (per-viewer — gate your buttons on these)
`can_roll`, `can_buy`, `can_build`, `can_mortgage`, `can_unmortgage`, `can_trade`, `can_end_turn`,
`can_pay_jail_fine`, `can_use_jail_card`, `can_bid`, `can_declare_bankruptcy` — all booleans.
A non-current player gets an all-`false` ActionSet **except** `can_bid` during an auction. The server
re-validates every intent, so these flags never advertise a move the engine would reject.

### SpaceOwnership (40 entries, index == board position)
`position`, `owner_id` (str|null — null = unowned/non-purchasable), `houses` (0–4),
`has_hotel` (bool), `is_mortgaged` (bool).

### AuctionState (non-null only in `auction` phase)
`property_position`, `bids` (`[{ "player_id", "amount" }]`), `highest_bid`,
`highest_bidder_id` (str|null), `time_remaining_ms`, `started_at_ms`.
Compute the live countdown as `max(0, time_remaining_ms - (now_ms - started_at_ms))`.

### TradeState (non-null only in `trade_negotiation` phase)
`id`, `proposer_id`, `target_id`, `proposer_offer` (TradeOffer), `target_request` (TradeOffer),
`status` (`pending` | `countered` | `accepted` | `rejected` | `cancelled`), `expires_at` (ISO).
Only `target_id` may respond — gate your "respond" UI on `trade.target_id === viewer_id`.

### ActiveCard (non-null briefly after drawing Chance/Community Chest)
`id`, `kind` (`chance` | `community_chest`), `text`, `drawer_id`, and `effect` — a discriminated union
on `type`:
- `{ "type":"advance_to", "position", "collect_go_bonus" }`
- `{ "type":"advance_to_nearest", "space_type":"railroad"|"utility", "pay_double" }`
- `{ "type":"go_to_jail" }`
- `{ "type":"go_back", "spaces" }`
- `{ "type":"collect", "amount" }` / `{ "type":"pay", "amount" }`
- `{ "type":"collect_from_each_player", "amount" }` / `{ "type":"pay_each_player", "amount" }`
- `{ "type":"get_out_of_jail_free" }`
- `{ "type":"repairs", "per_house", "per_hotel" }`

The card effect is **already applied** in the same snapshot (auto-resolve); `active_card` is for display
and clears on the next command.

### BankruptcyState (non-null in `bankrupt_resolution` phase)
`debtor_id`, `creditor_id` (str|null — null = owed to the bank), `amount_owed`. The debtor must raise
cash (sell/mortgage) until they can pay, or send `game.declare_bankruptcy`.

### LogEntry
`id`, `kind` (`event` for game events; `chat`/`sticker` are merged from the chat channel client-side),
`text`, `ts`, plus optional `player_id`, `player_name`, `player_token`, `sticker_url`.

---

## 4. Turn phase state machine

`turn.phase` values and what's valid in each (for the **current** player unless noted):

| phase | meaning | valid intents |
|-------|---------|---------------|
| `pre_roll` | start of turn | `roll_dice`; also `build/sell/mortgage/unmortgage`, `propose_trade` |
| `jail_decision` | current player is in jail | `roll_dice` (try doubles), `pay_jail_fine`, `use_jail_card` |
| `post_roll` | moved; resolve the tile | if `pending_buy_position`: `buy_property`/`pass_buy`; else `end_turn`; plus build/mortgage/trade |
| `must_pay_rent` | rent already auto-charged | `end_turn` (+ build/mortgage to raise cash) |
| `auction` | a declined property is up for bid | `place_bid` — **any** solvent player |
| `trade_negotiation` | a trade offer is pending | `respond_trade` — **the target only** |
| `bankrupt_resolution` | current player can't pay a debt | `mortgage`/`sell_house`, then `declare_bankruptcy` |
| `game_over` | game finished | none |

Notes: rolling doubles grants another roll (back to `pre_roll`); 3 doubles → jail. Landing on
Go-To-Jail / a `go_to_jail` card → jail with **no** extra roll. `pass_buy` opens an `auction`; the
[scheduler](#5-timers) closes it on timeout. Trades and auctions auto-expire on their timers.

---

## 5. Timers

Auctions and trades are time-boxed; a server-side scheduler advances them when their timer is **due**
and broadcasts the resulting `game.state` (no per-second spam while one is mid-flight). The FE just
renders `auction.time_remaining_ms`/`trade.expires_at` and waits for the broadcast on expiry.

---

## 6. Errors

Illegal/out-of-phase/out-of-turn game intents return a private `system.error` to the sender only
(not broadcast):

```json
{ "v": 1, "type": "system.error", "payload": { "code": "illegal_action", "message": "not your turn" } }
```

`code` is `illegal_action` for all engine rejections (wrong turn/phase, can't afford, even-build
violation, etc.). Envelope-level problems use the session protocol codes (`malformed`,
`unsupported_version`, `unknown_type`, …). A malformed/over-range payload (e.g. `position > 39`) is
rejected as `malformed`, not `illegal_action`.

On `seq` gaps or a `state conflict` error, treat the next received `game.state` as authoritative
(snapshots are full — no client-side patching needed).

---

## 7. Worked examples

### A normal turn (buy)
```
→ game.roll_dice {}
← game.state   turn.dice_roll set; player moved; if landed on an unowned property,
               turn.phase="post_roll", turn.pending_buy_position=<pos>, actions.can_buy=true
→ game.buy_property { "position": <pos> }
← game.state   spaces[pos].owner_id = you; balance debited; pending_buy_position=null; can_end_turn=true
→ game.end_turn {}
← game.state   turn.current_player_id = next player; phase="pre_roll" (or "jail_decision")
```

### Decline → auction
```
→ game.roll_dice {}             ← game.state  (landed on unowned property, can_buy=true)
→ game.pass_buy {}              ← game.state  auction != null, phase="auction"; every solvent player: can_bid=true
→ game.place_bid { "amount": 60 }  ← game.state  auction.highest_bid=60, highest_bidder_id=you
   …other players may bid…       (scheduler resolves on timeout)
← game.state                    auction=null, property owned by the winner, phase="post_roll"
```

### Game over
```
← game.state   status="finished", winner_id=<last solvent player>, turn.phase="game_over"
← session.updated   the session is now "finished"
```

---

## 8. Source of truth
| Topic | File |
|-------|------|
| Game state + nested models | `src/domain/game/schemas/state.py`, `src/domain/game/schemas/cards.py` |
| Action availability | `src/domain/game/rules/actions.py` |
| Intent payloads | `src/protocol/ws/schemas.py` |
| Intent handlers + registry | `src/gateway/handlers/game.py`, `src/gateway/handlers/__init__.py` |
| Per-viewer snapshot builder | `application/services/game_service.py::build_game_state_message` |
| Per-viewer broadcast | `src/gateway/backplane.py::publish_game_state` |
| Auction/trade timers | `src/application/services/game_scheduler.py` |
| Board data (names/prices/rent) | `src/domain/game/board_data.py` |
| Full ruleset reference | `docs/ruleset.md` (if present) |
