from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from domain.session.model import (
    MAX_SESSION_MEMBERS,
    MemberRole,
    Session,
    SessionStatus,
    SessionVisibility,
)
from infra.mongo.sessions.document import SessionDocument, SessionMemberDocument
from infra.mongo.sessions.mapper import (
    document_from_mongo,
    document_to_mongo,
    to_document,
    to_domain,
)


class SessionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db.sessions

    async def insert(self, doc: SessionDocument) -> Session:
        try:
            await self._collection.insert_one(document_to_mongo(doc))
        except DuplicateKeyError:
            raise
        return to_domain(doc)

    async def find_by_id(self, session_id: str) -> Session | None:
        raw = await self._collection.find_one({"_id": session_id})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def find_by_invite_code(self, invite_code: str) -> Session | None:
        raw = await self._collection.find_one({"invite_code": invite_code})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def delete(self, session_id: str) -> bool:
        result = await self._collection.delete_one({"_id": session_id})
        return result.deleted_count > 0

    async def list_public_waiting(
        self,
        *,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: str | None = None,
    ) -> list[Session]:
        query: dict[str, object] = {
            "status": SessionStatus.WAITING.value,
            "visibility": SessionVisibility.PUBLIC.value,
        }
        if cursor_created_at is not None and cursor_id is not None:
            query["$or"] = [
                {"created_at": {"$lt": cursor_created_at}},
                {"created_at": cursor_created_at, "_id": {"$lt": cursor_id}},
            ]

        cursor = (
            self._collection.find(query)
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit)
        )
        return [to_domain(document_from_mongo(raw)) async for raw in cursor]

    async def add_member(
        self,
        session_id: str,
        member: SessionMemberDocument,
    ) -> Session | None:
        now = datetime.now(UTC)
        raw = await self._collection.find_one_and_update(
            {
                "_id": session_id,
                "status": SessionStatus.WAITING.value,
                "members.user_id": {"$ne": member.user_id},
                "$expr": {"$lt": [{"$size": "$members"}, MAX_SESSION_MEMBERS]},
            },
            {
                "$push": {"members": member.model_dump()},
                "$set": {"updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def remove_member(self, session_id: str, user_id: str) -> Session | None:
        now = datetime.now(UTC)
        raw = await self._collection.find_one_and_update(
            {"_id": session_id},
            {
                "$pull": {"members": {"user_id": user_id}},
                "$set": {"updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def update_host_and_member_role(
        self,
        session_id: str,
        *,
        new_host_user_id: str,
    ) -> Session | None:
        now = datetime.now(UTC)
        session = await self.find_by_id(session_id)
        if session is None:
            return None

        updated_members = []
        for m in session.members:
            if m.user_id == new_host_user_id:
                updated_members.append(
                    SessionMemberDocument(
                        user_id=m.user_id,
                        display_name=m.display_name,
                        role=MemberRole.HOST,
                        joined_at=m.joined_at,
                    )
                )
            elif m.role == MemberRole.HOST:
                updated_members.append(
                    SessionMemberDocument(
                        user_id=m.user_id,
                        display_name=m.display_name,
                        role=MemberRole.PLAYER,
                        joined_at=m.joined_at,
                    )
                )
            else:
                updated_members.append(
                    SessionMemberDocument(
                        user_id=m.user_id,
                        display_name=m.display_name,
                        role=m.role,
                        joined_at=m.joined_at,
                    )
                )

        raw = await self._collection.find_one_and_update(
            {"_id": session_id},
            {
                "$set": {
                    "host_user_id": new_host_user_id,
                    "members": [m.model_dump() for m in updated_members],
                    "updated_at": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def set_status(
        self,
        session_id: str,
        status: SessionStatus,
        *,
        expected_status: SessionStatus | None = None,
    ) -> Session | None:
        now = datetime.now(UTC)
        query: dict[str, object] = {"_id": session_id}
        if expected_status is not None:
            query["status"] = expected_status.value

        raw = await self._collection.find_one_and_update(
            query,
            {"$set": {"status": status.value, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))
