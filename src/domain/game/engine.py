from __future__ import annotations

import random

from domain.game.board_data import get_board_space, is_purchasable
from domain.game.constants import DOUBLES_JAIL_THRESHOLD
from domain.game.enums import CardKind, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import Clock, roll_dice
from domain.game.schemas.commands import (
    AdvanceAuction,
    BuildHouse,
    BuyProperty,
    DeclareBankruptcy,
    EndTurn,
    ExpireTrade,
    GameCommand,
    Mortgage,
    PassBuy,
    PayJailFine,
    PlaceBid,
    PlayerCommand,
    ProposeTrade,
    RespondTrade,
    RollDice,
    SellHouse,
    SystemCommand,
    Unmortgage,
    UseJailCard,
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
from domain.game.schemas.state import DiceRoll, GameState
from domain.game.rules.actions import with_actions
from domain.game.rules.auction import is_auction_expired, place_bid, resolve_auction, start_auction
from domain.game.rules.bankruptcy import check_win_condition, resolve_bankruptcy
from domain.game.rules.payments import try_settle_debt
from domain.game.rules.building import build_house, mortgage_property, sell_house, unmortgage_property
from domain.game.rules.cards import return_jail_card_to_deck
from domain.game.rules.helpers import get_player_by_id_from_state, update_player_net_worth
from domain.game.rules.movement import (
    advance_position,
    apply_go_salary,
    resolve_landing,
    send_to_jail,
)
from domain.game.rules.trade import expire_trade, propose_trade, respond_trade

_BUILD_PHASES = frozenset({
    TurnPhase.PRE_ROLL,
    TurnPhase.POST_ROLL,
    TurnPhase.BANKRUPT_RESOLUTION,
})


def apply(
    state: GameState,
    command: GameCommand,
    *,
    rng: random.Random,
    clock: Clock,
    go_salary: int,
    jail_fine: int = 50,
) -> tuple[GameState, list[GameEvent]]:
    now_ms = int(clock.now().timestamp() * 1000)
    now = clock.now()

    if isinstance(command, (AdvanceAuction, ExpireTrade)):
        new_state, events = _handle_system(state, command, now_ms=now_ms, now=now)
    elif isinstance(command, (RespondTrade, PlaceBid)):
        # These come from a player who is NOT the current turn player: trade responses
        # from the trade target, and auction bids from any solvent player (an auction is
        # open to everyone, not just whoever's turn it is). Eligibility is validated
        # inside the respective rule (respond_trade / place_bid).
        new_state, events = _dispatch_player_command(
            state, command, rng, go_salary, jail_fine, now_ms=now_ms, now=now
        )
        return with_actions(new_state), events
    else:
        _assert_current_player(state, command.player_id)
        new_state, events = _dispatch_player_command(
            state, command, rng, go_salary, jail_fine, now_ms=now_ms, now=now
        )

    new_state = _clear_active_card(state, new_state, command)
    new_state = try_settle_debt(new_state)
    new_state = check_win_condition(new_state)
    new_state = _append_log(new_state, events, clock)
    return with_actions(new_state), events


def _dispatch_player_command(
    state: GameState,
    command: PlayerCommand,
    rng: random.Random,
    go_salary: int,
    jail_fine: int,
    *,
    now_ms: int,
    now,
) -> tuple[GameState, list[GameEvent]]:
    if isinstance(command, RollDice):
        return _handle_roll_dice(state, command, rng, go_salary, jail_fine)
    if isinstance(command, BuyProperty):
        return _handle_buy_property(state, command)
    if isinstance(command, PassBuy):
        return _handle_pass_buy(state, command, now_ms=now_ms)
    if isinstance(command, EndTurn):
        return _handle_end_turn(state, command)
    if isinstance(command, PayJailFine):
        return _handle_pay_jail_fine(state, command, jail_fine)
    if isinstance(command, UseJailCard):
        return _handle_use_jail_card(state, command)
    if isinstance(command, BuildHouse):
        return _handle_build_house(state, command)
    if isinstance(command, SellHouse):
        return _handle_sell_house(state, command)
    if isinstance(command, Mortgage):
        return _handle_mortgage(state, command)
    if isinstance(command, Unmortgage):
        return _handle_unmortgage(state, command)
    if isinstance(command, ProposeTrade):
        return _handle_propose_trade(state, command, now)
    if isinstance(command, RespondTrade):
        return _handle_respond_trade(state, command, now)
    if isinstance(command, PlaceBid):
        return _handle_place_bid(state, command)
    if isinstance(command, DeclareBankruptcy):
        return _handle_declare_bankruptcy(state, command)
    raise IllegalMove("unknown command")


def _assert_current_player(state: GameState, player_id: str) -> None:
    if state.turn.current_player_id != player_id:
        raise IllegalMove("not your turn")


def _clear_active_card(
    state: GameState,
    new_state: GameState,
    command: GameCommand,
) -> GameState:
    if state.active_card is not None and not isinstance(command, (AdvanceAuction, ExpireTrade)):
        return new_state.model_copy(update={"active_card": None})
    return new_state


def _handle_roll_dice(
    state: GameState,
    command: RollDice,
    rng: random.Random,
    go_salary: int,
    jail_fine: int,
) -> tuple[GameState, list[GameEvent]]:
    phase = state.turn.phase
    if phase not in (TurnPhase.PRE_ROLL, TurnPhase.JAIL_DECISION):
        raise IllegalMove("cannot roll dice in current phase")

    player = get_player_by_id_from_state(state, command.player_id)
    in_jail = player.jail_status is not None

    if in_jail and phase == TurnPhase.PRE_ROLL:
        raise IllegalMove("must resolve jail decision before rolling")

    die1, die2 = roll_dice(rng)
    is_doubles = die1 == die2
    dice_roll = DiceRoll(die1=die1, die2=die2, is_doubles=is_doubles)
    events: list[GameEvent] = []

    if in_jail:
        if is_doubles:
            freed = player.model_copy(update={"jail_status": None})
            return _execute_move(
                state,
                freed,
                die1 + die2,
                dice_roll,
                is_doubles=True,
                events=events,
                go_salary=go_salary,
                jail_fine=jail_fine,
                rng=rng,
                extra_roll_allowed=False,
            )

        remaining = player.jail_status.turns_remaining - 1  # type: ignore[union-attr]
        if remaining > 0:
            updated = player.model_copy(
                update={
                    "jail_status": player.jail_status.model_copy(update={"turns_remaining": remaining})  # type: ignore[union-attr]
                }
            )
            players = list(state.players)
            idx = next(i for i, p in enumerate(players) if p.id == player.id)
            players[idx] = update_player_net_worth(updated, state.spaces)
            new_turn = state.turn.model_copy(
                update={
                    "dice_roll": dice_roll,
                    "doubles_streak": 0,
                    "phase": TurnPhase.POST_ROLL,
                    "pending_buy_position": None,
                }
            )
            return state.model_copy(update={"players": tuple(players), "turn": new_turn}), events

        freed = player.model_copy(
            update={"jail_status": None, "balance": player.balance - jail_fine}
        )
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == player.id)
        players[idx] = update_player_net_worth(freed, state.spaces)
        state = state.model_copy(update={"players": tuple(players)})
        return _execute_move(
            state,
            freed,
            die1 + die2,
            dice_roll,
            is_doubles=False,
            events=events,
            go_salary=go_salary,
            jail_fine=jail_fine,
            rng=rng,
            extra_roll_allowed=False,
        )

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
        return state.model_copy(update={"players": tuple(players), "turn": new_turn}), events

    return _execute_move(
        state,
        player,
        die1 + die2,
        dice_roll,
        is_doubles,
        events,
        go_salary,
        jail_fine,
        rng,
        extra_roll_allowed=is_doubles,
    )


def _execute_move(
    state: GameState,
    player,
    steps: int,
    dice_roll: DiceRoll,
    is_doubles: bool,
    events: list[GameEvent],
    go_salary: int,
    jail_fine: int,
    rng: random.Random,
    *,
    extra_roll_allowed: bool,
) -> tuple[GameState, list[GameEvent]]:
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

    new_streak = state.turn.doubles_streak + 1 if is_doubles else 0
    if is_doubles and extra_roll_allowed:
        events.append(
            RolledDoubles(
                player_id=player.id,
                player_name=player.display_name,
                streak=new_streak,
            )
        )

    working, landing_events, sent_to_jail = resolve_landing(
        working,
        moved_player,
        dice_roll,
        go_salary=go_salary,
        rng=rng,
        jail_fine=jail_fine,
    )
    events.extend(landing_events)

    if sent_to_jail or working.bankruptcy is not None:
        phase = TurnPhase.POST_ROLL if sent_to_jail else working.turn.phase
        new_turn = working.turn.model_copy(
            update={
                "dice_roll": dice_roll,
                "doubles_streak": 0,
                "phase": phase,
                "pending_buy_position": working.turn.pending_buy_position,
            }
        )
        return working.model_copy(update={"turn": new_turn}), events

    if is_doubles and extra_roll_allowed:
        streak = new_streak
        if working.turn.pending_buy_position is not None:
            # Landed on a buyable tile: the player must resolve the purchase (buy/auction)
            # BEFORE taking the doubles extra roll. Stay in POST_ROLL and keep the pending
            # buy; the extra roll is deferred and granted once buy/pass is handled (the
            # >0 doubles_streak is the signal — see _handle_buy_property / resolve_auction).
            next_phase = TurnPhase.POST_ROLL
            pending_buy = working.turn.pending_buy_position
        else:
            next_phase = TurnPhase.PRE_ROLL
            pending_buy = None
    else:
        next_phase = working.turn.phase
        pending_buy = working.turn.pending_buy_position
        streak = 0

    new_turn = working.turn.model_copy(
        update={
            "dice_roll": dice_roll,
            "doubles_streak": streak,
            "phase": next_phase,
            "pending_buy_position": pending_buy,
        }
    )
    return working.model_copy(update={"turn": new_turn}), events


def _handle_pay_jail_fine(
    state: GameState,
    command: PayJailFine,
    jail_fine: int,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase != TurnPhase.JAIL_DECISION:
        raise IllegalMove("cannot pay jail fine in current phase")
    player = get_player_by_id_from_state(state, command.player_id)
    if player.jail_status is None:
        raise IllegalMove("not in jail")
    if player.balance < jail_fine:
        raise IllegalMove("insufficient funds for jail fine")

    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player.id)
    players[idx] = update_player_net_worth(
        player.model_copy(update={"jail_status": None, "balance": player.balance - jail_fine}),
        state.spaces,
    )
    new_turn = state.turn.model_copy(update={"phase": TurnPhase.PRE_ROLL})
    return state.model_copy(update={"players": tuple(players), "turn": new_turn}), []


def _handle_use_jail_card(
    state: GameState,
    command: UseJailCard,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase != TurnPhase.JAIL_DECISION:
        raise IllegalMove("cannot use jail card in current phase")
    player = get_player_by_id_from_state(state, command.player_id)
    if player.jail_status is None:
        raise IllegalMove("not in jail")
    if player.get_out_of_jail_cards <= 0:
        raise IllegalMove("no get out of jail free cards")

    state = return_jail_card_to_deck(state, CardKind.CHANCE, "chance_08")

    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player.id)
    players[idx] = update_player_net_worth(
        player.model_copy(
            update={
                "jail_status": None,
                "get_out_of_jail_cards": player.get_out_of_jail_cards - 1,
            }
        ),
        state.spaces,
    )
    new_turn = state.turn.model_copy(update={"phase": TurnPhase.PRE_ROLL})
    return state.model_copy(update={"players": tuple(players), "turn": new_turn}), []


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

    # If the player rolled doubles, the extra roll was deferred until the purchase was
    # resolved — grant it now by returning to PRE_ROLL.
    next_phase = TurnPhase.PRE_ROLL if state.turn.doubles_streak > 0 else state.turn.phase
    new_turn = state.turn.model_copy(
        update={"pending_buy_position": None, "phase": next_phase}
    )
    event = PropertyBought(
        player_id=player.id,
        player_name=player.display_name,
        position=command.position,
        property_name=board_space.name,
        price=price,
    )
    return state.model_copy(
        update={"players": tuple(players), "spaces": tuple(spaces), "turn": new_turn}
    ), [event]


def _handle_pass_buy(
    state: GameState,
    command: PassBuy,
    *,
    now_ms: int,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in (TurnPhase.POST_ROLL, TurnPhase.MUST_PAY_RENT):
        raise IllegalMove("cannot pass buy in current phase")

    pending = state.turn.pending_buy_position
    if pending is None:
        raise IllegalMove("no property to pass on")

    player = get_player_by_id_from_state(state, command.player_id)
    board_space = get_board_space(pending)
    event = BuyDeclined(
        player_id=player.id,
        player_name=player.display_name,
        position=pending,
        property_name=board_space.name,
    )
    return start_auction(state, pending, now_ms), [event]


def _handle_end_turn(
    state: GameState,
    command: EndTurn,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in (
        TurnPhase.POST_ROLL,
        TurnPhase.MUST_PAY_RENT,
        TurnPhase.BANKRUPT_RESOLUTION,
    ):
        raise IllegalMove("cannot end turn in current phase")

    if state.turn.pending_buy_position is not None:
        raise IllegalMove("must buy or pass on property before ending turn")

    if state.bankruptcy is not None:
        raise IllegalMove("must resolve bankruptcy before ending turn")

    active_players = [p for p in state.players if not p.is_bankrupt]
    current_idx = next(
        i for i, p in enumerate(active_players) if p.id == state.turn.current_player_id
    )
    next_idx = (current_idx + 1) % len(active_players)
    next_player = active_players[next_idx]

    round_number = state.turn.round_number
    if next_idx <= current_idx:
        round_number += 1

    event = TurnEnded(
        player_id=command.player_id,
        player_name=get_player_by_id_from_state(state, command.player_id).display_name,
        next_player_id=next_player.id,
        next_player_name=next_player.display_name,
    )

    next_phase = (
        TurnPhase.JAIL_DECISION if next_player.jail_status is not None else TurnPhase.PRE_ROLL
    )

    new_turn = state.turn.model_copy(
        update={
            "phase": next_phase,
            "current_player_id": next_player.id,
            "turn_number": state.turn.turn_number + 1,
            "round_number": round_number,
            "dice_roll": None,
            "doubles_streak": 0,
            "pending_buy_position": None,
        }
    )
    return state.model_copy(update={"turn": new_turn}), [event]


def _handle_build_house(
    state: GameState,
    command: BuildHouse,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in _BUILD_PHASES:
        raise IllegalMove("cannot build in current phase")
    return build_house(state, command.player_id, command.position), []


def _handle_sell_house(
    state: GameState,
    command: SellHouse,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in _BUILD_PHASES:
        raise IllegalMove("cannot sell in current phase")
    return sell_house(state, command.player_id, command.position), []


def _handle_mortgage(
    state: GameState,
    command: Mortgage,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in _BUILD_PHASES:
        raise IllegalMove("cannot mortgage in current phase")
    return mortgage_property(state, command.player_id, command.position), []


def _handle_unmortgage(
    state: GameState,
    command: Unmortgage,
) -> tuple[GameState, list[GameEvent]]:
    if state.turn.phase not in _BUILD_PHASES:
        raise IllegalMove("cannot unmortgage in current phase")
    return unmortgage_property(state, command.player_id, command.position), []


def _handle_propose_trade(state, command, now) -> tuple[GameState, list[GameEvent]]:
    return propose_trade(
        state,
        command.player_id,
        command.target_id,
        command.proposer_offer,
        command.target_request,
        now,
    ), []


def _handle_respond_trade(state, command, now) -> tuple[GameState, list[GameEvent]]:
    return respond_trade(
        state,
        command.player_id,
        command.trade_id,
        command.response,
        command.counter_offer,
        now,
    ), []


def _handle_place_bid(state, command) -> tuple[GameState, list[GameEvent]]:
    return place_bid(state, command.player_id, command.amount), []


def _handle_declare_bankruptcy(state, command) -> tuple[GameState, list[GameEvent]]:
    if state.bankruptcy is None:
        raise IllegalMove("not in bankruptcy resolution")
    if state.bankruptcy.debtor_id != command.player_id:
        raise IllegalMove("not the debtor")
    return resolve_bankruptcy(state, command.player_id), []


def _handle_system(
    state: GameState,
    command: SystemCommand,
    *,
    now_ms: int,
    now,
) -> tuple[GameState, list[GameEvent]]:
    if isinstance(command, AdvanceAuction):
        if state.auction is None or not is_auction_expired(state, now_ms):
            return state, []
        return resolve_auction(state), []
    if isinstance(command, ExpireTrade):
        if state.trade is None or state.trade.expires_at > now:
            return state, []
        return expire_trade(state), []
    return state, []


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
