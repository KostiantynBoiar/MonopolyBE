from __future__ import annotations

import random
from datetime import datetime
from uuid import uuid4

from domain.game.board_data import BOARD
from domain.game.constants import BANK_HOTELS, BANK_HOUSES, TOKEN_COLORS
from domain.game.enums import GameStatus, TurnPhase
from domain.game.rng import Clock
from domain.game.rules.cards import initial_chance_deck, initial_chest_deck
from domain.game.schemas.state import (
    GameState,
    PlayerState,
    SpaceOwnership,
    TurnState,
)


class GameMember:
    def __init__(self, user_id: str, display_name: str) -> None:
        self.user_id = user_id
        self.display_name = display_name


def new_game(
    *,
    game_id: str,
    session_code: str,
    members: list[GameMember],
    rng: random.Random,
    clock: Clock,
    starting_balance: int = 1500,
) -> GameState:
    now = clock.now()
    member_order = list(members)
    rng.shuffle(member_order)

    players: list[PlayerState] = []
    for turn_order, member in enumerate(member_order):
        players.append(
            PlayerState(
                id=uuid4().hex,
                user_id=member.user_id,
                display_name=member.display_name,
                token=TOKEN_COLORS[turn_order % len(TOKEN_COLORS)],
                turn_order=turn_order,
                balance=starting_balance,
                net_worth=starting_balance,
            )
        )

    spaces = tuple(SpaceOwnership(position=space.position) for space in BOARD)

    current_player = players[0]
    return GameState(
        game_id=game_id,
        session_code=session_code,
        status=GameStatus.IN_PROGRESS,
        created_at=now,
        started_at=now,
        players=tuple(players),
        turn=TurnState(
            phase=TurnPhase.PRE_ROLL,
            current_player_id=current_player.id,
            turn_number=1,
            round_number=1,
        ),
        spaces=spaces,
        bank_houses=BANK_HOUSES,
        bank_hotels=BANK_HOTELS,
        chance_deck=initial_chance_deck(rng),
        chest_deck=initial_chest_deck(rng),
    )
