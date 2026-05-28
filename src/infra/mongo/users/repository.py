from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from core.exceptions import DuplicateEmailError
from domain.user.model import User
from infra.mongo.users.mapper import document_from_mongo, document_to_mongo, to_document, to_domain


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db.users

    async def find_by_email(self, email: str) -> User | None:
        raw = await self._collection.find_one({"email": email.lower()})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def find_by_id(self, user_id: str) -> User | None:
        raw = await self._collection.find_one({"_id": user_id})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def find_password_hash_by_email(self, email: str) -> tuple[User, str] | None:
        raw = await self._collection.find_one({"email": email.lower()})
        if raw is None:
            return None
        doc = document_from_mongo(raw)
        return to_domain(doc), doc.password_hash

    async def create(self, email: str, display_name: str, password_hash: str) -> User:
        doc = to_document(
            email=email.lower(),
            display_name=display_name,
            password_hash=password_hash,
        )
        try:
            await self._collection.insert_one(document_to_mongo(doc))
        except DuplicateKeyError as exc:
            raise DuplicateEmailError("Email already registered") from exc
        return to_domain(doc)
