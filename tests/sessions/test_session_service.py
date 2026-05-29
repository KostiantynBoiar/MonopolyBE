from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI

from application.services.session_service import SessionService
from core.exceptions import (
    ForbiddenHostActionError,
    NotMemberError,
    SessionFullError,
    SessionNotJoinableError,
)
from core.invite_code import INVITE_CODE_PATTERN
from core.security import hash_password
from domain.session.model import SessionStatus, SessionVisibility
from infra.mongo.users.repository import UserRepository


@pytest.mark.asyncio
async def test_create_session(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), _ = mongo_user_pair
    session = await session_service.create(host_id, visibility=SessionVisibility.PUBLIC)

    assert session.status == SessionStatus.WAITING
    assert session.visibility == SessionVisibility.PUBLIC
    assert session.host_user_id == host_id
    assert session.member_count() == 1
    assert INVITE_CODE_PATTERN.match(session.invite_code)


@pytest.mark.asyncio
async def test_list_public_lobby_excludes_private(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), _ = mongo_user_pair
    public = await session_service.create(host_id, visibility=SessionVisibility.PUBLIC)
    await session_service.create(host_id, visibility=SessionVisibility.PRIVATE)

    items, _ = await session_service.list_public_lobby()
    ids = {s.id for s in items}
    assert public.id in ids
    assert all(s.visibility == SessionVisibility.PUBLIC for s in items)
    assert all(s.status == SessionStatus.WAITING for s in items)


@pytest.mark.asyncio
async def test_join_and_assert_member(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), (guest_id, _) = mongo_user_pair
    session = await session_service.create(host_id)

    joined = await session_service.join(session.id, guest_id)
    assert joined.member_count() == 2

    result = await session_service.assert_member(session.id, guest_id)
    assert result.id == session.id


@pytest.mark.asyncio
async def test_assert_member_rejects_non_member(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), (guest_id, _) = mongo_user_pair
    session = await session_service.create(host_id)

    with pytest.raises(NotMemberError):
        await session_service.assert_member(session.id, guest_id)


@pytest.mark.asyncio
async def test_join_by_code_private(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), (guest_id, _) = mongo_user_pair
    session = await session_service.create(host_id, visibility=SessionVisibility.PRIVATE)

    joined = await session_service.join_by_code(session.invite_code, guest_id)
    assert joined.has_member(guest_id)


@pytest.mark.asyncio
async def test_kick_requires_host(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), (guest_id, _) = mongo_user_pair
    session = await session_service.create(host_id)
    await session_service.join(session.id, guest_id)

    with pytest.raises(ForbiddenHostActionError):
        await session_service.kick(session.id, guest_id, host_id)


@pytest.mark.asyncio
async def test_start_changes_status(
    session_service: SessionService, mongo_user_pair: tuple
) -> None:
    (host_id, _), (guest_id, _) = mongo_user_pair
    session = await session_service.create(host_id)

    started = await session_service.start(session.id, host_id)
    assert started.status == SessionStatus.IN_PROGRESS

    with pytest.raises(SessionNotJoinableError):
        await session_service.join(session.id, guest_id)


@pytest.mark.asyncio
async def test_session_full(
    session_service: SessionService,
    mongo_user_pair: tuple,
    mongo_app: FastAPI,
) -> None:
    (host_id, _), _ = mongo_user_pair
    session = await session_service.create(host_id)
    repo = UserRepository(mongo_app.state.mongo.db)

    for i in range(7):
        user = await repo.create(
            email=f"extra{i}_{uuid4().hex[:8]}@example.com",
            display_name=f"Player {i}",
            password_hash=hash_password("password123"),
        )
        await session_service.join(session.id, user.id)

    last = await repo.create(
        email=f"overflow_{uuid4().hex[:8]}@example.com",
        display_name="Overflow",
        password_hash=hash_password("password123"),
    )
    with pytest.raises(SessionFullError):
        await session_service.join(session.id, last.id)
