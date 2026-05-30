from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import Settings, get_settings
from core.exceptions import GameNotFoundError, GameVersionConflictError, NotMemberError
from domain.game import engine
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.actions import with_actions
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
    ProposeTrade,
    RespondTrade,
    RollDice,
    SellHouse,
    SystemCommand,
    Unmortgage,
    UseJailCard,
)
from domain.game.schemas.state import GameState
from domain.game.setup import GameMember, new_game
from domain.session.schemas import Session
from infra.mongo.games.repository import GameRepository
from protocol.ws.envelope import make_outbound

_session_locks: dict[str, asyncio.Lock] = {}


def _lock_for(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


class GameService:
    def __init__(
        self,
        games: GameRepository,
        settings: Settings,
    ) -> None:
        self._games = games
        self._settings = settings

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase, settings: Settings | None = None) -> GameService:
        return cls(
            games=GameRepository(db),
            settings=settings or get_settings(),
        )

    async def start_game(self, session: Session) -> GameState:
        existing = await self._games.find_by_session_id(session.id)
        if existing is not None:
            return with_actions(existing.state)

        game_id = uuid4().hex
        seed = random.randint(0, 2**31 - 1)
        rng = random.Random(seed)
        clock = FixedClock(datetime.now(UTC))
        members = [
            GameMember(user_id=m.user_id, display_name=m.display_name)
            for m in session.members
        ]
        state = new_game(
            game_id=game_id,
            session_code=session.invite_code,
            members=members,
            rng=rng,
            clock=clock,
            starting_balance=self._settings.game_starting_balance,
        )
        state = with_actions(state)
        rng_state = GameRepository.serialize_rng(rng)
        doc = GameRepository.build_document(
            game_id=game_id,
            session_id=session.id,
            seed=seed,
            rng_state=rng_state,
            state=state,
        )
        stored = await self._games.insert(doc)
        return stored.state

    async def get_active_game(self, session_id: str) -> GameState | None:
        stored = await self._games.find_by_session_id(session_id)
        if stored is None:
            return None
        return with_actions(stored.state)

    async def apply_intent(
        self,
        session_id: str,
        user_id: str,
        command: GameCommand,
    ) -> GameState:
        async with _lock_for(session_id):
            stored = await self._games.find_by_session_id(session_id)
            if stored is None:
                raise GameNotFoundError(session_id)

            if isinstance(command, SystemCommand):
                resolved = command
            else:
                player_id = self._resolve_player_id(stored.state, user_id)
                resolved = _with_player_id(command, player_id)

            rng = GameRepository.restore_rng(stored.rng_state)
            clock = FixedClock(datetime.now(UTC))

            try:
                new_state, _ = engine.apply(
                    stored.state,
                    resolved,
                    rng=rng,
                    clock=clock,
                    go_salary=self._settings.go_salary,
                    jail_fine=self._settings.jail_fine,
                )
            except IllegalMove:
                raise

            rng_state = GameRepository.serialize_rng(rng)
            updated = await self._games.update_with_version(
                stored.game_id,
                new_state,
                stored.version,
                rng_state,
            )
            if updated is None:
                raise GameVersionConflictError(session_id)
            return updated.state

    def snapshot_message(self, state: GameState, viewer_user_id: str | None = None) -> dict:
        player_id = None
        if viewer_user_id is not None:
            for player in state.players:
                if player.user_id == viewer_user_id:
                    player_id = player.id
                    break
        snapshot = with_actions(state, player_id)
        payload = snapshot.model_dump(mode="json")
        if player_id is not None:
            payload["viewer_id"] = player_id
        return make_outbound("game.state", payload)

    @staticmethod
    def _resolve_player_id(state: GameState, user_id: str) -> str:
        for player in state.players:
            if player.user_id == user_id:
                return player.id
        raise NotMemberError(state.game_id, user_id)


def _with_player_id(command: GameCommand, player_id: str) -> GameCommand:
    if isinstance(command, RollDice):
        return RollDice(player_id=player_id)
    if isinstance(command, BuyProperty):
        return BuyProperty(player_id=player_id, position=command.position)
    if isinstance(command, PassBuy):
        return PassBuy(player_id=player_id)
    if isinstance(command, EndTurn):
        return EndTurn(player_id=player_id)
    if isinstance(command, PayJailFine):
        return PayJailFine(player_id=player_id)
    if isinstance(command, UseJailCard):
        return UseJailCard(player_id=player_id)
    if isinstance(command, BuildHouse):
        return BuildHouse(player_id=player_id, position=command.position)
    if isinstance(command, SellHouse):
        return SellHouse(player_id=player_id, position=command.position)
    if isinstance(command, Mortgage):
        return Mortgage(player_id=player_id, position=command.position)
    if isinstance(command, Unmortgage):
        return Unmortgage(player_id=player_id, position=command.position)
    if isinstance(command, ProposeTrade):
        return ProposeTrade(
            player_id=player_id,
            target_id=command.target_id,
            proposer_offer=command.proposer_offer,
            target_request=command.target_request,
        )
    if isinstance(command, RespondTrade):
        return RespondTrade(
            player_id=player_id,
            trade_id=command.trade_id,
            response=command.response,
            counter_offer=command.counter_offer,
        )
    if isinstance(command, PlaceBid):
        return PlaceBid(player_id=player_id, amount=command.amount)
    if isinstance(command, DeclareBankruptcy):
        return DeclareBankruptcy(player_id=player_id)
    return command
