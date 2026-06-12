from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from typing_extensions import Self

from core.exceptions import (
    CannotKickSelfError,
    ForbiddenHostActionError,
    NotFoundError,
    NotMemberError,
    SessionFullError,
    SessionNotFoundError,
    SessionNotJoinableError,
)
from core.constants import SESSION_INVITE_CODE_MAX_RETRIES
from core.invite_code import generate_invite_code, normalize_invite_code
from domain.game.enums import GameMode
from domain.session.schemas import (
    MemberRole,
    Session,
    SessionStatus,
    SessionVisibility,
)
from infra.mongo.sessions.document import SessionMemberDocument
from infra.mongo.sessions.mapper import to_document
from infra.mongo.sessions.repository import SessionRepository
from infra.mongo.users.repository import UserRepository


class SessionService:
    def __init__(
        self,
        session_repo: SessionRepository,
        user_repo: UserRepository,
    ) -> None:
        self._sessions = session_repo
        self._users = user_repo

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase) -> Self:  # type: ignore[type-arg]
        return cls(SessionRepository(db), UserRepository(db))

    async def create(
        self,
        user_id: str,
        visibility: SessionVisibility = SessionVisibility.PUBLIC,
        ranked: bool = True,
        game_mode: GameMode = GameMode.NORMAL,
    ) -> Session:
        user = await self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        now = datetime.now(UTC)
        host_member = SessionMemberDocument(
            user_id=user.id,
            display_name=user.display_name,
            role=MemberRole.HOST,
            joined_at=now,
            rating=user.rating,
            calibration_complete=user.calibration_complete,
        )

        for _ in range(SESSION_INVITE_CODE_MAX_RETRIES):
            doc = to_document(
                invite_code=generate_invite_code(),
                host_user_id=user.id,
                status=SessionStatus.WAITING,
                visibility=visibility,
                game_mode=game_mode,
                ranked=ranked,
                members=[host_member],
            )
            try:
                return await self._sessions.insert(doc)
            except DuplicateKeyError:
                continue

        raise RuntimeError("Failed to generate unique invite code")

    async def list_public_lobby(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Session], str | None]:
        cursor_created_at: datetime | None = None
        cursor_id: str | None = None
        if cursor:
            cursor_created_at, cursor_id = self._decode_cursor(cursor)

        sessions = await self._sessions.list_public_waiting(
            limit=limit + 1,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )

        next_cursor: str | None = None
        if len(sessions) > limit:
            sessions = sessions[:limit]
            last = sessions[-1]
            next_cursor = self._encode_cursor(last.created_at, last.id)

        return sessions, next_cursor

    async def get(self, session_id: str, user_id: str) -> Session:
        session = await self._get_session_or_404(session_id)
        if session.has_member(user_id):
            return session
        if (
            session.visibility == SessionVisibility.PUBLIC
            and session.status == SessionStatus.WAITING
        ):
            return session
        raise NotMemberError(session_id, user_id)

    async def get_by_code(self, invite_code: str, user_id: str) -> Session:
        normalized = normalize_invite_code(invite_code)
        session = await self._sessions.find_by_invite_code(normalized)
        if session is None:
            raise SessionNotFoundError()
        if session.has_member(user_id):
            return session
        if session.status == SessionStatus.WAITING:
            return session
        raise SessionNotJoinableError(session.id, session.status.value)

    async def join(self, session_id: str, user_id: str) -> Session:
        session = await self._get_session_or_404(session_id)
        return await self._join_session(session, user_id)

    async def join_by_code(self, invite_code: str, user_id: str) -> Session:
        normalized = normalize_invite_code(invite_code)
        session = await self._sessions.find_by_invite_code(normalized)
        if session is None:
            raise SessionNotFoundError()
        return await self._join_session(session, user_id)

    async def leave(self, session_id: str, user_id: str) -> Session | None:
        """Remove a member. Returns the updated session, or None if it was deleted
        (last member left)."""
        session = await self._get_session_or_404(session_id)
        if not session.has_member(user_id):
            raise NotMemberError(session_id, user_id)

        updated = await self._sessions.remove_member(session_id, user_id)
        if updated is None:
            raise SessionNotFoundError()

        if not updated.members:
            await self._sessions.delete(session_id)
            return None

        if updated.host_user_id == user_id:
            new_host = min(updated.members, key=lambda m: m.joined_at)
            rehosted = await self._sessions.update_host_and_member_role(
                session_id,
                new_host_user_id=new_host.user_id,
            )
            if rehosted is not None:
                return rehosted

        return updated

    async def kick(self, session_id: str, host_user_id: str, target_user_id: str) -> Session:
        session = await self._get_session_or_404(session_id)
        if not session.is_host(host_user_id):
            raise ForbiddenHostActionError()
        if host_user_id == target_user_id:
            raise CannotKickSelfError()
        if not session.has_member(target_user_id):
            raise NotMemberError(session_id, target_user_id)
        if session.status != SessionStatus.WAITING:
            raise SessionNotJoinableError(session_id, session.status.value)

        updated = await self._sessions.remove_member(session_id, target_user_id)
        if updated is None:
            raise SessionNotFoundError()
        return updated

    async def start(self, session_id: str, host_user_id: str) -> Session:
        session = await self._get_session_or_404(session_id)
        if not session.is_host(host_user_id):
            raise ForbiddenHostActionError()
        if session.status != SessionStatus.WAITING:
            raise SessionNotJoinableError(session_id, session.status.value)

        updated = await self._sessions.set_status(
            session_id,
            SessionStatus.IN_PROGRESS,
            expected_status=SessionStatus.WAITING,
        )
        if updated is None:
            raise SessionNotJoinableError(session_id, session.status.value)
        return updated

    async def mark_finished(self, session_id: str) -> Session | None:
        """Flip an in-progress session to finished. Returns the updated session, or
        None if it wasn't in_progress (already finished / idempotent no-op)."""
        return await self._sessions.set_status(
            session_id,
            SessionStatus.FINISHED,
            expected_status=SessionStatus.IN_PROGRESS,
        )

    async def assert_member(self, session_id: str, user_id: str) -> Session:
        session = await self._sessions.find_by_id(session_id)
        if session is None or not session.has_member(user_id):
            raise NotMemberError(session_id, user_id)
        return session

    async def _join_session(self, session: Session, user_id: str) -> Session:
        if session.has_member(user_id):
            return session
        if session.status != SessionStatus.WAITING:
            raise SessionNotJoinableError(session.id, session.status.value)
        if session.is_full():
            raise SessionFullError(session.id)

        user = await self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        member = SessionMemberDocument(
            user_id=user.id,
            display_name=user.display_name,
            role=MemberRole.PLAYER,
            joined_at=datetime.now(UTC),
            rating=user.rating,
            calibration_complete=user.calibration_complete,
        )
        updated = await self._sessions.add_member(session.id, member, session.max_players)
        if updated is not None:
            return updated

        current = await self._sessions.find_by_id(session.id)
        if current is None:
            raise SessionNotFoundError()
        if current.has_member(user_id):
            return current
        if current.status != SessionStatus.WAITING:
            raise SessionNotJoinableError(session.id, current.status.value)
        if current.is_full():
            raise SessionFullError(session.id)
        raise SessionNotJoinableError(session.id, current.status.value)

    async def _get_session_or_404(self, session_id: str) -> Session:
        session = await self._sessions.find_by_id(session_id)
        if session is None:
            raise SessionNotFoundError()
        return session

    @staticmethod
    def _encode_cursor(created_at: datetime, session_id: str) -> str:
        return f"{created_at.isoformat()}|{session_id}"

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str]:
        created_at_str, session_id = cursor.split("|", 1)
        return datetime.fromisoformat(created_at_str), session_id
