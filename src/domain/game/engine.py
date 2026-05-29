from __future__ import annotations

import random

from domain.game.board_data import get_board_space, is_purchasable
from domain.game.constants import DOUBLES_JAIL_THRESHOLD
from domain.game.exceptions import IllegalMove
from domain.game.rng import Clock, roll_dice
from domain.game.schemas.commands import (
    BuyProperty,
    EndTurn,
    GameCommand,
    PassBuy,
    RollDice,
)
from domain.game.schemas.events import (
    BuyDeclined,
    GameEvent,
    PlayerMoved,
    PropertyBought,
    RolledDoubles,
    SentToJail,
    TurnEnded,
    event_to_log_entry,
)
from domain.game.schemas.state import DiceRoll, GameState, TurnPhase
from domain.game.rules.actions import with_actions
from domain.game.rules.helpers import get_player_by_id_from_state, update_player_net_worth
from domain.game.rules.movement import (
    advance_position,
    apply_go_salary,
    resolve_landing,
    send_to_jail,
)


def apply(
    state: GameState,
    command: GameCommand,
    *,
    rng: random.Random,
    clock: Clock,
    go_salary: int,
) -> tuple[GameState, list[GameEvent]]:
    _assert_current_player(state, command.player_id)

    if isinstance(command, RollDice):
        new_state, events = _handle_roll_dice(state, command, rng, go_salary)
    elif isinstance(command, BuyProperty):
        new_state, events = _handle_buy_property(state, command)
    elif isinstance(command, PassBuy):
        new_state, events = _handle_pass_buy(state, command)
    elif isinstance(command, EndTurn):
        new_state, events = _handle_end_turn(state, command)
    else:
        raise IllegalMove("unknown command")

    new_state = _append_log(new_state, events, clock)
    return with_actions(new_state), events


def _assert_current_player(state: GameState, player_id: str) -> None:
    if state.turn.current_player_id != player_id:
        raise IllegalMove("not your turn")


def _handle_roll_dice(
    state: GameState,
    command: RollDice,
    rng: random.Random,
    go_salary: int,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase != TurnPhase.PRE_ROLL:
        raise IllegalMove("cannot roll dice in current phase")

    player = get_player_by_id_from_state(state, command.player_id)
    die1, die2 = roll_dice(rng)
    is_doubles = die1 == die2
    dice_roll = DiceRoll(die1=die1, die2=die2, is_doubles=is_doubles)
    events: list[GameEvent] = []

    in_jail = player.jail_status is not None
    if in_jail:
        if is_doubles:
            player = player.model_copy(update={"jail_status": None})
        else:
            new_turn = state.turn.model_copy(
                update={
                    "dice_roll": dice_roll,
                    "doubles_streak": 0,
                    "phase": TurnPhase.POST_ROLL,
                    "pending_buy_position": None,
                }
            )
            new_state = state.model_copy(update={"turn": new_turn})
            return new_state, events

    new_streak = state.turn.doubles_streak + 1 if is_doubles else 0

    if is_doubles and new_streak >= DOUBLES_JAIL_THRESHOLD:
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == player.id)
        jailed = send_to_jail(player)
        players[idx] = update_player_net_worth(jailed, state.spaces)
        events.append(
            SentToJail(
                player_id=player.id,
                player_name=player.display_name,
                reason="three doubles in a row",
            )
        )
        new_turn = state.turn.model_copy(
            update={
                "dice_roll": dice_roll,
                "doubles_streak": 0,
                "phase": TurnPhase.POST_ROLL,
                "pending_buy_position": None,
            }
        )
        new_state = state.model_copy(update={"players": tuple(players), "turn": new_turn})
        return new_state, events

    steps = die1 + die2
    new_pos, passed_go = advance_position(player.position, steps)
    moved_player = player.model_copy(update={"position": new_pos})
    events.append(
        PlayerMoved(
            player_id=player.id,
            player_name=player.display_name,
            player_token=player.token,
            from_position=player.position,
            to_position=new_pos,
            dice_total=steps,
        )
    )

    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player.id)
    players[idx] = moved_player
    working = state.model_copy(update={"players": tuple(players)})

    if passed_go:
        working, go_event = apply_go_salary(working, moved_player, go_salary)
        events.append(go_event)
        moved_player = get_player_by_id_from_state(working, player.id)

    if is_doubles:
        events.append(
            RolledDoubles(
                player_id=player.id,
                player_name=player.display_name,
                streak=new_streak,
            )
        )

    working, landing_events = resolve_landing(
        working,
        moved_player,
        dice_roll,
        go_salary=go_salary,
    )
    events.extend(landing_events)

    if is_doubles:
        next_phase = TurnPhase.PRE_ROLL
        pending_buy = None
    else:
        next_phase = working.turn.phase
        pending_buy = working.turn.pending_buy_position

    new_turn = working.turn.model_copy(
        update={
            "dice_roll": dice_roll,
            "doubles_streak": new_streak if is_doubles else 0,
            "phase": next_phase,
            "pending_buy_position": pending_buy,
        }
    )
    return working.model_copy(update={"turn": new_turn}), events


def _handle_buy_property(
    state: GameState,
    command: BuyProperty,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in (TurnPhase.POST_ROLL, TurnPhase.MUST_PAY_RENT):
        raise IllegalMove("cannot buy property in current phase")

    pending = state.turn.pending_buy_position
    if pending is None or pending != command.position:
        raise IllegalMove("property is not available to buy")

    if not is_purchasable(command.position):
        raise IllegalMove("space is not purchasable")

    ownership = state.spaces[command.position]
    if ownership.owner_id is not None:
        raise IllegalMove("property already owned")

    player = get_player_by_id_from_state(state, command.player_id)
    board_space = get_board_space(command.position)
    price = board_space.price
    if price is None:
        raise IllegalMove("space has no price")

    if player.balance < price:
        raise IllegalMove("insufficient funds")

    spaces = list(state.spaces)
    spaces[command.position] = ownership.model_copy(update={"owner_id": player.id})

    owned = list(player.owned_positions)
    owned.append(command.position)
    updated_player = player.model_copy(
        update={
            "balance": player.balance - price,
            "owned_positions": tuple(sorted(owned)),
        }
    )
    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player.id)
    players[idx] = update_player_net_worth(updated_player, tuple(spaces))

    new_turn = state.turn.model_copy(update={"pending_buy_position": None})
    event = PropertyBought(
        player_id=player.id,
        player_name=player.display_name,
        position=command.position,
        property_name=board_space.name,
        price=price,
    )
    new_state = state.model_copy(
        update={
            "players": tuple(players),
            "spaces": tuple(spaces),
            "turn": new_turn,
        }
    )
    return new_state, [event]


def _handle_pass_buy(
    state: GameState,
    command: PassBuy,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in (TurnPhase.POST_ROLL, TurnPhase.MUST_PAY_RENT):
        raise IllegalMove("cannot pass buy in current phase")

    pending = state.turn.pending_buy_position
    if pending is None:
        raise IllegalMove("no property to pass on")

    player = get_player_by_id_from_state(state, command.player_id)
    board_space = get_board_space(pending)
    new_turn = state.turn.model_copy(update={"pending_buy_position": None})
    event = BuyDeclined(
        player_id=player.id,
        player_name=player.display_name,
        position=pending,
        property_name=board_space.name,
    )
    return state.model_copy(update={"turn": new_turn}), [event]


def _handle_end_turn(
    state: GameState,
    command: EndTurn,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in (TurnPhase.POST_ROLL, TurnPhase.MUST_PAY_RENT):
        raise IllegalMove("cannot end turn in current phase")

    if state.turn.pending_buy_position is not None:
        raise IllegalMove("must buy or pass on property before ending turn")

    active_players = [p for p in state.players if not p.is_bankrupt]
    current_idx = next(
        i for i, p in enumerate(active_players) if p.id == state.turn.current_player_id
    )
    next_idx = (current_idx + 1) % len(active_players)
    next_player = active_players[next_idx]

    round_number = state.turn.round_number
    if next_idx <= current_idx:
        round_number += 1

    turn_number = state.turn.turn_number + 1
    event = TurnEnded(
        player_id=command.player_id,
        player_name=get_player_by_id_from_state(state, command.player_id).display_name,
        next_player_id=next_player.id,
        next_player_name=next_player.display_name,
    )

    new_turn = state.turn.model_copy(
        update={
            "phase": TurnPhase.PRE_ROLL,
            "current_player_id": next_player.id,
            "turn_number": turn_number,
            "round_number": round_number,
            "dice_roll": None,
            "doubles_streak": 0,
            "pending_buy_position": None,
        }
    )
    return state.model_copy(update={"turn": new_turn}), [event]


def _append_log(
    state: GameState,
    events: list[GameEvent],
    clock: Clock,
) -> GameState:
    if not events:
        return state
    ts = clock.now()
    new_entries = state.log + tuple(event_to_log_entry(e, ts) for e in events)
    return state.model_copy(update={"log": new_entries})
