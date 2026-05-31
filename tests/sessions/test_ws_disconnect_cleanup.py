"""Disconnect cleanup logic (gateway._cleanup_on_disconnect).

We test the cleanup function directly against a real session service rather than via the
TestClient WebSocket: Starlette's TestClient doesn't drive the server's WS handler task to
its `finally` block after the client disconnects (it only completes at lifespan shutdown),
so the on-disconnect cleanup can't be observed there — though it fires promptly under real
uvicorn. Calling the function directly tests the actual behavior deterministically.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager

from application.services.session_service import SessionService
from core.security import hash_password
from domain.session.schemas import SessionVisibility
from gateway import router as ws_router_mod
from gateway.router import _remove_if_still_gone, _schedule_removal
from infra.mongo.users.repository import UserRepository
from main import create_app


class _FakeConn:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class _FakeManager:
    """Stands in for ConnectionManager: returns the connections still 'present'."""

    def __init__(self, conns: list[_FakeConn]) -> None:
        self._conns = conns

    def local_connections(self, _session_id: str):
        return frozenset(self._conns)


class _FakeBackplane:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, session_id: str, msg: dict) -> None:
        self.published.append((session_id, msg))


@pytest.fixture
async def db():
    app = create_app()
    async with LifespanManager(app):
        yield app.state.mongo.db


async def _user(db, label: str):
    return await UserRepository(db).create(
        email=f"{label}_{uuid4().hex[:8]}@example.com",
        display_name=label.title(),
        password_hash=hash_password("password123"),
    )


@pytest.mark.asyncio
async def test_cleanup_deletes_room_when_last_member_disconnects(db) -> None:
    host = await _user(db, "host")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)

    # Host's last connection is gone (manager reports none remaining).
    await _remove_if_still_gone(_FakeManager([]), _FakeBackplane(), svc, session.id, host.id)

    assert await svc._sessions.find_by_id(session.id) is None  # room deleted


@pytest.mark.asyncio
async def test_cleanup_removes_member_and_broadcasts_when_others_remain(db) -> None:
    host = await _user(db, "host")
    guest = await _user(db, "guest")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)
    await svc.join(session.id, guest.id)

    backplane = _FakeBackplane()
    # Guest disconnects; host still connected.
    await _remove_if_still_gone(
        _FakeManager([_FakeConn(host.id)]), backplane, svc, session.id, guest.id
    )

    remaining = await svc._sessions.find_by_id(session.id)
    assert remaining is not None
    assert all(m.user_id != guest.id for m in remaining.members)
    assert len(backplane.published) == 1  # session.updated broadcast


@pytest.mark.asyncio
async def test_cleanup_keeps_member_with_another_connection(db) -> None:
    host = await _user(db, "host")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)

    # The user still has another live connection → must NOT be removed.
    await _remove_if_still_gone(
        _FakeManager([_FakeConn(host.id)]), _FakeBackplane(), svc, session.id, host.id
    )

    assert await svc._sessions.find_by_id(session.id) is not None


@pytest.mark.asyncio
async def test_cleanup_skips_in_progress_session(db) -> None:
    host = await _user(db, "host")
    guest = await _user(db, "guest")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)
    await svc.join(session.id, guest.id)
    await svc.start(session.id, host.id)  # in_progress

    # Guest disconnects from an in-progress game → must stay a member.
    await _remove_if_still_gone(_FakeManager([]), _FakeBackplane(), svc, session.id, guest.id)

    remaining = await svc._sessions.find_by_id(session.id)
    assert remaining is not None
    assert any(m.user_id == guest.id for m in remaining.members)


@pytest.mark.asyncio
async def test_grace_removal_cancelled_on_reconnect(db, monkeypatch) -> None:
    host = await _user(db, "host")
    guest = await _user(db, "guest")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)
    await svc.join(session.id, guest.id)

    monkeypatch.setattr(ws_router_mod, "WS_DISCONNECT_GRACE_S", 0.2)
    # Guest drops → removal scheduled; guest reconnects (cancel) before grace elapses.
    _schedule_removal(_FakeManager([_FakeConn(host.id)]), _FakeBackplane(), svc, session.id, guest.id)
    ws_router_mod._cancel_pending_removal(session.id, guest.id)
    await asyncio.sleep(0.3)

    remaining = await svc._sessions.find_by_id(session.id)
    assert remaining is not None
    assert any(m.user_id == guest.id for m in remaining.members)  # NOT evicted


@pytest.mark.asyncio
async def test_grace_removal_fires_after_window(db, monkeypatch) -> None:
    host = await _user(db, "host")
    guest = await _user(db, "guest")
    svc = SessionService.from_db(db)
    session = await svc.create(host.id, SessionVisibility.PUBLIC)
    await svc.join(session.id, guest.id)

    monkeypatch.setattr(ws_router_mod, "WS_DISCONNECT_GRACE_S", 0.1)
    # Guest drops and never reconnects → removed after the grace window.
    _schedule_removal(_FakeManager([_FakeConn(host.id)]), _FakeBackplane(), svc, session.id, guest.id)
    await asyncio.sleep(0.3)

    remaining = await svc._sessions.find_by_id(session.id)
    assert remaining is not None
    assert all(m.user_id != guest.id for m in remaining.members)
