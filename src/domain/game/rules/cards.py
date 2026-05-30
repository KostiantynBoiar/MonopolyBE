from __future__ import annotations

import random

from domain.game.cards_data import ALL_CARDS, DEFAULT_CHANCE_DECK, DEFAULT_CHEST_DECK
from domain.game.constants import (
    CARD_LANDING_RECURSION_LIMIT,
    RAILROAD_POSITIONS,
    UTILITY_POSITIONS,
)
from domain.game.enums import CardKind
from domain.game.schemas.cards import (
    ActiveCard,
    AdvanceToEffect,
    AdvanceToNearestEffect,
    CardDef,
    CollectEffect,
    CollectFromEachPlayerEffect,
    GetOutOfJailFreeEffect,
    GoBackEffect,
    GoToJailEffect,
    PayEachPlayerEffect,
    PayEffect,
    RepairsEffect,
)
from domain.game.schemas.events import CardDrawn, SentToJail
from domain.game.schemas.state import DiceRoll, GameState, PlayerState
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    refresh_all_net_worth,
    update_player_net_worth,
)
from domain.game.rules.movement import (
    advance_position,
    apply_go_salary,
    resolve_landing,
    send_to_jail,
)
from domain.game.rules.payments import attempt_payment


def initial_chance_deck(rng: random.Random) -> tuple[str, ...]:
    deck = list(DEFAULT_CHANCE_DECK)
    rng.shuffle(deck)
    return tuple(deck)


def initial_chest_deck(rng: random.Random) -> tuple[str, ...]:
    deck = list(DEFAULT_CHEST_DECK)
    rng.shuffle(deck)
    return tuple(deck)


def draw_card(state: GameState, kind: CardKind, rng: random.Random) -> tuple[GameState, CardDef]:
    if kind == CardKind.CHANCE:
        deck = list(state.chance_deck)
    else:
        deck = list(state.chest_deck)

    if not deck:
        if kind == CardKind.CHANCE:
            deck = list(DEFAULT_CHANCE_DECK)
        else:
            deck = list(DEFAULT_CHEST_DECK)
        rng.shuffle(deck)

    card_id = deck.pop(0)
    card = ALL_CARDS[card_id]

    if isinstance(card.effect, GetOutOfJailFreeEffect):
        new_deck = tuple(deck)
    else:
        deck.append(card_id)
        new_deck = tuple(deck)

    if kind == CardKind.CHANCE:
        state = state.model_copy(update={"chance_deck": new_deck})
    else:
        state = state.model_copy(update={"chest_deck": new_deck})

    return state, card


def return_jail_card_to_deck(state: GameState, kind: CardKind, card_id: str) -> GameState:
    if kind == CardKind.CHANCE:
        deck = state.chance_deck + (card_id,)
        return state.model_copy(update={"chance_deck": deck})
    deck = state.chest_deck + (card_id,)
    return state.model_copy(update={"chest_deck": deck})


def nearest_position(from_pos: int, targets: frozenset[int]) -> int:
    for steps in range(1, 40):
        pos = (from_pos + steps) % 40
        if pos in targets:
            return pos
    raise RuntimeError("no nearest position found")


def apply_card_effect(
    state: GameState,
    player: PlayerState,
    card: CardDef,
    *,
    dice_roll: DiceRoll,
    go_salary: int,
    jail_fine: int,
    rng: random.Random,
    recursion_depth: int = 0,
) -> tuple[GameState, list, bool]:
    """Apply a card effect. Returns (state, events, sent_to_jail)."""
    events: list = []
    sent_to_jail = False
    effect = card.effect

    if isinstance(effect, AdvanceToEffect):
        new_pos, passed_go = advance_position(player.position, _steps_to(player.position, effect.position))
        moved = player.model_copy(update={"position": new_pos})
        state, _ = _set_player(state, moved)
        if passed_go and effect.collect_go_bonus:
            state, go_event = apply_go_salary(state, moved, go_salary)
            events.append(go_event)
            moved = get_player_by_id_from_state(state, player.id)
        state, landing_events, jail = resolve_landing(
            state, moved, dice_roll, go_salary=go_salary, recursion_depth=recursion_depth, rng=rng, jail_fine=jail_fine
        )
        events.extend(landing_events)
        return state, events, sent_to_jail or jail

    if isinstance(effect, AdvanceToNearestEffect):
        targets = RAILROAD_POSITIONS if effect.space_type == "railroad" else UTILITY_POSITIONS
        target = nearest_position(player.position, targets)
        new_pos, passed_go = advance_position(
            player.position, _steps_to(player.position, target)
        )
        moved = player.model_copy(update={"position": new_pos})
        state, _ = _set_player(state, moved)
        if passed_go:
            state, go_event = apply_go_salary(state, moved, go_salary)
            events.append(go_event)
            moved = get_player_by_id_from_state(state, player.id)
        state, landing_events, jail = resolve_landing(
            state,
            moved,
            dice_roll,
            go_salary=go_salary,
            recursion_depth=recursion_depth,
            rent_multiplier=2 if effect.pay_double else 1,
            rng=rng,
            jail_fine=jail_fine,
        )
        events.extend(landing_events)
        return state, events, sent_to_jail or jail

    if isinstance(effect, GoToJailEffect):
        jailed = send_to_jail(player)
        state, _ = _set_player(state, jailed)
        events.append(
            SentToJail(
                player_id=player.id,
                player_name=player.display_name,
                reason="Chance/Community Chest card",
            )
        )
        return state, events, True

    if isinstance(effect, GoBackEffect):
        new_pos = (player.position - effect.spaces) % 40
        moved = player.model_copy(update={"position": new_pos})
        state, _ = _set_player(state, moved)
        if recursion_depth >= CARD_LANDING_RECURSION_LIMIT:
            return state, events, sent_to_jail
        state, landing_events, jail = resolve_landing(
            state, moved, dice_roll, go_salary=go_salary, recursion_depth=recursion_depth + 1,
            rng=rng, jail_fine=jail_fine,
        )
        events.extend(landing_events)
        return state, events, sent_to_jail or jail

    if isinstance(effect, CollectEffect):
        updated = player.model_copy(update={"balance": player.balance + effect.amount})
        state, _ = _set_player(state, updated)
        return state, events, sent_to_jail

    if isinstance(effect, PayEffect):
        state, events = _pay_from_player(state, player, effect.amount, creditor_id=None)
        return state, events, sent_to_jail

    if isinstance(effect, CollectFromEachPlayerEffect):
        players = list(state.players)
        idx = _player_index(players, player.id)
        total = 0
        for i, other in enumerate(players):
            if other.id == player.id or other.is_bankrupt:
                continue
            pay = min(effect.amount, other.balance)
            players[i] = update_player_net_worth(
                other.model_copy(update={"balance": other.balance - pay}),
                state.spaces,
            )
            total += pay
        receiver = get_player_by_id_from_state(
            state.model_copy(update={"players": tuple(players)}), player.id
        )
        players[idx] = update_player_net_worth(
            receiver.model_copy(update={"balance": receiver.balance + total}),
            state.spaces,
        )
        state = state.model_copy(update={"players": tuple(players)})
        return state, events, sent_to_jail

    if isinstance(effect, PayEachPlayerEffect):
        players = list(state.players)
        idx = _player_index(players, player.id)
        total = 0
        for other in state.players:
            if other.id == player.id or other.is_bankrupt:
                continue
            total += effect.amount
        payer = player.model_copy(update={"balance": player.balance - total})
        players[idx] = update_player_net_worth(payer, state.spaces)
        for i, other in enumerate(players):
            if other.id == player.id or other.is_bankrupt:
                continue
            players[i] = update_player_net_worth(
                other.model_copy(update={"balance": other.balance + effect.amount}),
                state.spaces,
            )
        state = state.model_copy(update={"players": refresh_all_net_worth(
            state.model_copy(update={"players": tuple(players)})
        )})
        return state, events, sent_to_jail

    if isinstance(effect, GetOutOfJailFreeEffect):
        updated = player.model_copy(
            update={"get_out_of_jail_cards": player.get_out_of_jail_cards + 1}
        )
        state, _ = _set_player(state, updated)
        return state, events, sent_to_jail

    if isinstance(effect, RepairsEffect):
        cost = 0
        for pos in player.owned_positions:
            ownership = state.spaces[pos]
            if ownership.has_hotel:
                cost += effect.per_hotel
            else:
                cost += effect.per_house * ownership.houses
        state, events = _pay_from_player(state, player, cost, creditor_id=None)
        return state, events, sent_to_jail

    return state, events, sent_to_jail


def draw_and_apply(
    state: GameState,
    player: PlayerState,
    kind: CardKind,
    *,
    rng: random.Random,
    dice_roll: DiceRoll,
    go_salary: int,
    jail_fine: int,
    recursion_depth: int = 0,
) -> tuple[GameState, list, ActiveCard, bool]:
    state, card = draw_card(state, kind, rng)
    active = ActiveCard(
        id=card.id,
        kind=card.kind,
        text=card.text,
        effect=card.effect,
        drawer_id=player.id,
    )
    events: list = [CardDrawn(
        player_id=player.id,
        player_name=player.display_name,
        card_id=card.id,
        card_text=card.text,
        kind=card.kind.value,
    )]
    state, effect_events, sent_to_jail = apply_card_effect(
        state,
        get_player_by_id_from_state(state, player.id),
        card,
        dice_roll=dice_roll,
        go_salary=go_salary,
        jail_fine=jail_fine,
        rng=rng,
        recursion_depth=recursion_depth,
    )
    events.extend(effect_events)
    return state, events, active, sent_to_jail


def _steps_to(from_pos: int, to_pos: int) -> int:
    if to_pos >= from_pos:
        return to_pos - from_pos
    return 40 - from_pos + to_pos


def _set_player(state: GameState, player: PlayerState) -> tuple[GameState, None]:
    players = list(state.players)
    idx = _player_index(players, player.id)
    players[idx] = update_player_net_worth(player, state.spaces)
    new_state = state.model_copy(
        update={"players": refresh_all_net_worth(
            state.model_copy(update={"players": tuple(players)})
        )}
    )
    return new_state, None


def _pay_from_player(
    state: GameState,
    player: PlayerState,
    amount: int,
    *,
    creditor_id: str | None,
) -> tuple[GameState, list]:

    return attempt_payment(state, player.id, amount, creditor_id=creditor_id)


def _player_index(players: list[PlayerState], player_id: str) -> int:
    for i, p in enumerate(players):
        if p.id == player_id:
            return i
    raise KeyError(player_id)
