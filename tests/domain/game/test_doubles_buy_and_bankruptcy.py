"""Regressions: buying on a doubles roll, and bankruptcy not softlocking the turn."""

from __future__ import annotations

from domain.game.enums import GameStatus, TurnPhase
from domain.game.rng import FixedClock
from domain.game.rules.actions import compute_actions
from domain.game.rules.auction import resolve_auction
from domain.game.rules.helpers import space_at
from domain.game.schemas.commands import BuyProperty, DeclareBankruptcy, PassBuy, RollDice
from domain.game.schemas.state import BankruptcyState, GameState
from domain.game.setup import GameMember, new_game
from tests.domain.game.conftest import SequencedRandom, apply_cmd

# From GO (1), doubles [3,3] lands on 7 = Oriental Ave.
_ORIENTAL = 7


def _three_player_game(clock: FixedClock) -> GameState:
    return new_game(
        game_id="g",
        session_code="TYC-3P",
        members=[GameMember("ua", "A"), GameMember("ub", "B"), GameMember("uc", "C")],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        starting_balance=1500,
    )


def test_doubles_landing_on_buyable_allows_buy_then_extra_roll(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1 = two_player_game.players[0]
    rolled, _ = apply_cmd(two_player_game, RollDice(player_id=p1.id), clock, rng_values=[3, 3])

    # Must resolve the purchase first — NOT jump straight to the re-roll.
    assert rolled.turn.phase == TurnPhase.POST_ROLL
    assert rolled.turn.pending_buy_position == _ORIENTAL
    assert rolled.turn.doubles_streak == 1

    actions = compute_actions(rolled, p1.id)
    assert actions.can_buy is True
    assert actions.can_roll is False  # can't roll again until buy/pass is resolved

    bought, _ = apply_cmd(rolled, BuyProperty(player_id=p1.id, position=_ORIENTAL), clock)
    # The deferred doubles extra roll is granted once the property is bought.
    assert bought.turn.phase == TurnPhase.PRE_ROLL
    assert bought.turn.pending_buy_position is None
    assert space_at(bought.spaces, _ORIENTAL).owner_id == p1.id


def test_doubles_pass_buy_grants_extra_roll_after_auction(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1 = two_player_game.players[0]
    rolled, _ = apply_cmd(two_player_game, RollDice(player_id=p1.id), clock, rng_values=[3, 3])
    assert rolled.turn.pending_buy_position == _ORIENTAL

    auctioned, _ = apply_cmd(rolled, PassBuy(player_id=p1.id), clock)
    assert auctioned.auction is not None
    assert auctioned.turn.doubles_streak == 1  # streak rides through the auction

    resolved = resolve_auction(auctioned)
    assert resolved.turn.phase == TurnPhase.PRE_ROLL  # extra roll granted post-auction


def test_bankruptcy_advances_turn_and_does_not_softlock(clock: FixedClock) -> None:
    state = _three_player_game(clock)
    a, b, c = state.players
    state = state.model_copy(
        update={
            "bankruptcy": BankruptcyState(debtor_id=b.id, creditor_id=a.id, amount_owed=2000),
            "turn": state.turn.model_copy(
                update={"current_player_id": b.id, "phase": TurnPhase.BANKRUPT_RESOLUTION}
            ),
        }
    )

    after, _ = apply_cmd(state, DeclareBankruptcy(player_id=b.id), clock)

    assert after.players[1].is_bankrupt is True
    assert after.status == GameStatus.IN_PROGRESS  # A and C still in the game
    # The turn must move OFF the bankrupt player to the next active one (C), not stay on B.
    assert after.turn.current_player_id == c.id
    assert after.turn.phase == TurnPhase.PRE_ROLL
    assert after.bankruptcy is None

    # The crux of the softlock: play must continue normally. Before the fix the bankrupt
    # player stayed current and any subsequent turn action blew up (StopIteration over
    # active players). C should now be able to take their turn.
    rolled, _ = apply_cmd(after, RollDice(player_id=c.id), clock, rng_values=[1, 2])
    assert rolled.turn.current_player_id == c.id  # C's own turn proceeds, no crash


def test_two_player_bankruptcy_still_ends_game(clock: FixedClock) -> None:
    state = new_game(
        game_id="g2",
        session_code="TYC-2P",
        members=[GameMember("ua", "A"), GameMember("ub", "B")],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        starting_balance=1500,
    )
    a, b = state.players
    state = state.model_copy(
        update={
            "bankruptcy": BankruptcyState(debtor_id=b.id, creditor_id=a.id, amount_owed=2000),
            "turn": state.turn.model_copy(
                update={"current_player_id": b.id, "phase": TurnPhase.BANKRUPT_RESOLUTION}
            ),
        }
    )

    after, _ = apply_cmd(state, DeclareBankruptcy(player_id=b.id), clock)
    assert after.status == GameStatus.FINISHED
    assert after.winner_id == a.id
