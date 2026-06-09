# Duel Game Mode — Implementation Plan

## Context

The backend has a single standard 40-tile Monopoly board and no concept of game modes. The task is to add a **"duel"** mode with:

- Max 2 players, $1000 starting cash
- 1 six-sided die (not 2)
- A compact 23-tile board (positions 41–63, no ID collision with standard 0–39)
- Sudden death: at the 20-minute mark, if no one is bankrupt, highest net_worth wins immediately

The "20 Tiles Total" in the spec is a miscount — the user confirmed the explicit 23-tile row layout is correct.

---

## Central Architectural Problem

`state.spaces` is a tuple where `spaces[i].position == i` for the standard board (positions 0–39 equal tuple indices). Duel board positions 41–63 break this direct-index pattern.

**Fix**: Every `spaces[position]` → `spaces[position - go_position]`, where `go_position` is 0 for standard and 41 for duel. `go_position` is derivable from `spaces[0].position` (when only the tuple is available) or from `get_config(state.game_mode).go_position` (when state is available). Standard mode is unaffected because `pos - 0 = pos`.

---

## New Files

### `src/domain/game/game_config.py`

Frozen `GameConfig` dataclass + `get_config(mode) → GameConfig`:

```python
@dataclass(frozen=True)
class GameConfig:
    mode: GameMode
    board_size: int          # 40 or 23
    go_position: int         # 0 or 41
    jail_position: int       # 10 or 46
    goto_jail_position: int  # 30 or 58
    utility_positions: frozenset[int]   # {12,28} or {49}
    railroad_positions: frozenset[int]  # {5,15,25,35} or frozenset()
    board: tuple[BoardSpace, ...]
    chance_cards: tuple[CardDef, ...]
    default_chance_deck: tuple[str, ...]
    default_chest_deck: tuple[str, ...]
    dice_count: int          # 2 or 1
    max_players: int         # 8 or 2
    starting_balance: int    # 1500 or 1000
```

Two module-level instances: `STANDARD_CONFIG` and `DUEL_CONFIG`.

### `src/domain/game/modes/duel_cards.py`

12 duel-specific chance cards (IDs prefixed `duel_chance_`):

- `duel_chance_01`: Advance to GO (pos 41, collect bonus)
- `duel_chance_02`: Advance to DarkBlue1 (pos 62, collect bonus)
- `duel_chance_03`: Advance to DarkBlue2 (pos 63, no bonus)
- `duel_chance_04`: AdvanceToNearest utility (Electric at 49)
- `duel_chance_05`: GoToJail
- `duel_chance_06`: GoBack 3 spaces
- `duel_chance_07`: Collect $50
- `duel_chance_08`: GetOutOfJailFree
- `duel_chance_09`: Pay $15
- `duel_chance_10`: Collect $150
- `duel_chance_11`: RepairsEffect ($25/house, $100/hotel)
- `duel_chance_12`: PayEachPlayer $50

Exports `DUEL_CHANCE_CARDS` and `DEFAULT_DUEL_CHANCE_DECK`.

---

## Files to Modify

### Phase 1 — Enums & domain models (pure additions)

**`src/domain/game/enums.py`**
Add: `class GameMode(StrEnum): STANDARD = "standard"; DUEL = "duel"`

**`src/domain/game/schemas/state.py`**
Add two fields to `GameState`:

```python
game_mode: GameMode = GameMode.STANDARD
sudden_death_deadline_ms: int | None = None
```

**`src/domain/game/schemas/commands.py`**
Add `SuddenDeath` system command (no fields needed):

```python
class SuddenDeath(BaseModel):
    model_config = ConfigDict(frozen=True)
```

Add to `SystemCommand` union type.

**`src/domain/game/schemas/events.py`**
Add `SuddenDeathTriggered` event; include in `event_to_log_entry`.

### Phase 2 — Board data

**`src/domain/game/board_data.py`**
Add `DUEL_BOARD: tuple[BoardSpace, ...]` with 23 tiles (positions 41–63):

| Pos | Tile         | Price | Color/Type         |
| --- | ------------ | ----- | ------------------ |
| 41  | GO           | —     | CORNER             |
| 42  | Brown 1      | $60   | BROWN, house=$50   |
| 43  | Brown 2      | $60   | BROWN, house=$50   |
| 44  | Income Tax   | —     | TAX, $150          |
| 45  | Chance       | —     | CHANCE             |
| 46  | Jail         | —     | CORNER             |
| 47  | Light Blue 1 | $100  | CYAN, house=$50    |
| 48  | Light Blue 2 | $100  | CYAN, house=$50    |
| 49  | Electric Co. | $150  | UTILITY            |
| 50  | Orange 1     | $160  | ORANGE, house=$100 |
| 51  | Orange 2     | $160  | ORANGE, house=$100 |
| 52  | Free Parking | —     | CORNER             |
| 53  | Red 1        | $200  | RED, house=$100    |
| 54  | Red 2        | $200  | RED, house=$100    |
| 55  | Chance       | —     | CHANCE             |
| 56  | Yellow 1     | $240  | YELLOW, house=$150 |
| 57  | Yellow 2     | $240  | YELLOW, house=$150 |
| 58  | Go To Jail   | —     | CORNER             |
| 59  | Green 1      | $280  | GREEN, house=$150  |
| 60  | Green 2      | $280  | GREEN, house=$150  |
| 61  | Luxury Tax   | —     | TAX, $150          |
| 62  | Dark Blue 1  | $320  | BLUE, house=$200   |
| 63  | Dark Blue 2  | $400  | BLUE, house=$200   |

Rent tables: use equivalent standard Monopoly rent values for the same color group/price point.

Add `ALL_BOARDS_BY_POSITION: dict[int, BoardSpace]` merging both boards. Update `get_board_space` and `is_purchasable` to use it — no caller changes needed.

### Phase 3 — Space indexing fixes (most pervasive, all mechanical)

Pattern for every file: `spaces[pos]` → `spaces[pos - go_pos]` where `go_pos = spaces[0].position` (when only tuple is available) or `get_config(state.game_mode).go_position` (when state is available).

**`src/domain/game/rules/helpers.py`**

- `compute_net_worth`: `go_pos = spaces[0].position`; `spaces[pos - go_pos]` in loop
- `player_owns_full_color_group`, `player_has_rent_monopoly`: same pattern
- `count_owned_railroads(player, spaces)`: derive config from `spaces[0].position`, use `config.railroad_positions`
- `count_owned_utilities(player, spaces)`: same with `config.utility_positions`
- `positions_in_color_group(color_group, board=None)`: add optional `board` param; default to `BOARD` for standard; callers with state pass `get_config(state.game_mode).board`

**`src/domain/game/rules/movement.py`**

- `advance_position(from_pos, steps, *, board_size=40, go_position=0)`: offset-aware arithmetic (existing calls work with defaults)
- `send_to_jail(player, jail_position=JAIL_POSITION)`: parameterize jail position
- `resolve_landing`: `go_pos = get_config(state.game_mode).go_position`; `spaces[player.position - go_pos]`

**`src/domain/game/rules/cards.py`**

- `nearest_position(from_pos, targets, *, board_size=40, go_position=0)`: offset-aware loop
- `_steps_to(from_pos, to_pos, *, board_size=40, go_position=0)`: `board_size - local_from + local_to` pattern
- `GoBackEffect` handler: `((player.position - go_pos - effect.spaces) % board_size) + go_pos`
- `AdvanceToNearestEffect` handler: use `config.railroad_positions` / `config.utility_positions`; pass board params
- `draw_card`: use `config.chance_cards` tuple as card registry instead of global `ALL_CARDS`
- `initial_duel_chance_deck(rng)`: new function using `DEFAULT_DUEL_CHANCE_DECK`

**`src/domain/game/rules/building.py`**

- All `spaces[pos]` → `spaces[pos - go_pos]`; derive `go_pos = spaces[0].position` at function start
- All `positions_in_color_group(...)` calls → pass `config.board`

**`src/domain/game/rules/rent.py`**

- `spaces[position]` → `spaces[position - go_pos]` where `go_pos = spaces[0].position`

**`src/domain/game/rules/trade.py`**, **`rules/auction.py`**, **`rules/surrender.py`**, **`rules/bankruptcy.py`**

- Same `spaces[pos - go_pos]` pattern
- `bankruptcy.py`: bankrupt player's reset position → `go_position` (not hardcoded `0`)

**`src/domain/game/rules/actions.py`**

- Any `state.spaces[pending]` or similar → `state.spaces[pending - go_pos]`

**`src/domain/game/engine.py`**

- All `spaces[position]` / `state.spaces[position]` accesses → offset-adjusted
- All `advance_position(...)` calls → pass `board_size=config.board_size, go_position=config.go_position`
- All `send_to_jail(...)` calls → pass `jail_position=config.jail_position`
- All `positions_in_color_group(...)` calls → pass `config.board`
- `_handle_roll_dice`: single-die branch:
  ```python
  config = get_config(state.game_mode)
  if config.dice_count == 1:
      die1, _ = roll_dice(rng)
      die2, is_doubles = 0, False
  else:
      die1, die2 = roll_dice(rng)
      is_doubles = die1 == die2
  ```
- `_handle_system`: add `SuddenDeath` branch → `_handle_sudden_death(state, now_ms)`
- `_handle_sudden_death`: find highest net_worth non-bankrupt player; if no tie → set winner, FINISHED
- `return_jail_card_to_deck` call: use `config.jail_card_id` (add to `GameConfig`)

### Phase 4 — Game setup

**`src/domain/game/setup.py`**
`new_game` signature → `new_game(*, game_id, session_code, members, rng, clock, game_mode=GameMode.STANDARD)`:

- Derive `config = get_config(game_mode)`
- `starting_balance = config.starting_balance`
- `spaces = tuple(SpaceOwnership(position=space.position) for space in config.board)` (23 or 40 elements)
- Players start at `position=config.go_position` (41 for duel, 0 for standard)
- `chance_deck = initial_duel_chance_deck(rng) if game_mode == GameMode.DUEL else initial_chance_deck(rng)`
- `chest_deck = () if game_mode == GameMode.DUEL else initial_chest_deck(rng)`
- `sudden_death_deadline_ms = int(now.timestamp()*1000) + 20*60*1000 if game_mode == GameMode.DUEL else None`
- Set `game_mode=game_mode` and `sudden_death_deadline_ms=...` on returned `GameState`

### Phase 5 — Sudden death scheduler

**`src/application/services/game_scheduler.py`**
In `_tick_one`, after existing TurnTimeout/auction/trade checks, add:

```python
elif (
    state.game_mode == GameMode.DUEL
    and state.sudden_death_deadline_ms is not None
    and now_ms >= state.sudden_death_deadline_ms
    and state.status == GameStatus.IN_PROGRESS
):
    command = SuddenDeath()
```

### Phase 6 — Session & API layer

**`src/domain/session/schemas.py`**

- Add `game_mode: GameMode = GameMode.STANDARD`
- Add `max_players: int = MAX_SESSION_MEMBERS` (set at creation from config)
- `is_full()` → uses `self.max_players`

**`src/infra/mongo/sessions/document.py`**

- Add `game_mode: str = "standard"` and `max_players: int = 8`

**`src/infra/mongo/sessions/mapper.py`** (check path)

- Round-trip `game_mode` and `max_players` in both directions

**`src/infra/mongo/sessions/repository.py`**

- Atomic `add_member` guard uses stored `max_players`:
  ```
  "$expr": {"$lt": [{"$size": "$members"}, {"$ifNull": ["$max_players", MAX_SESSION_MEMBERS]}]}
  ```

**`src/application/services/session_service.py`**

- `create(user_id, visibility, ranked, game_mode=GameMode.STANDARD)`:
  - `max_players = get_config(game_mode).max_players`
  - Pass `game_mode` and `max_players` to `to_document`

**`src/application/services/game_service.py`**

- `start_game(session)` → pass `game_mode=session.game_mode` to `new_game`
- Remove `starting_balance=self._settings.game_starting_balance` (config owns this now)

**`src/protocol/rest/sessions.py`**

- `CreateSessionRequest`: add `game_mode: GameMode = GameMode.STANDARD`
- `SessionSummary`: add `game_mode: GameMode = GameMode.STANDARD`; `max_players` is already there, now populated from session

**`src/api/sessions/router.py`**

- `_to_summary`: pass `game_mode=session.game_mode, max_players=session.max_players`
- `create_session`: pass `game_mode=body.game_mode` to `service.create`

---

## Verification

1. **Unit tests** for `advance_position` with duel params:
   - `advance_position(41, 6, board_size=23, go_position=41)` → `(47, False)`
   - `advance_position(63, 3, board_size=23, go_position=41)` → `(43, True)` (wraps past GO)

2. **Unit tests** for `_steps_to` and `nearest_position` with duel board

3. **Integration test** — create a duel game, assert:
   - `state.spaces[0].position == 41`
   - Both players start at position 41
   - Die rolls move within 41–63 range
   - Landing on position 42 is purchasable
   - Sudden death: set deadline to `now_ms - 1`, apply `SuddenDeath()`, assert FINISHED with correct winner

4. **Regression** — run existing test suite; standard mode unaffected because `go_position=0` and all new params default to standard values

5. **Session API** — `POST /sessions {"game_mode": "duel"}` returns `max_players: 2`; third join attempt rejected
