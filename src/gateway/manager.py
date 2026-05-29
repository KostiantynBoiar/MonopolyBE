from __future__ import annotations

from collections import defaultdict
from sqlite3 import Connection


class ConnectionManager:
    def __init__(self) -> None:
        self._sessions: defaultdict[str, set[Connection]] = defaultdict(set)

    def register(self, conn: Connection) -> None:
        self._sessions[conn.session_id].add(conn)

    def unregister(self, conn: Connection) -> None:
        bucket = self._sessions.get(conn.session_id)
        if bucket:
            bucket.discard(conn)
            if not bucket:
                del self._sessions[conn.session_id]

    def local_connections(self, session_id: str) -> frozenset[Connection]:
        return frozenset(self._sessions.get(session_id, set()))

    def count(self, session_id: str) -> int:
        return len(self._sessions.get(session_id, set()))

    def all_connections(self) -> list[Connection]:
        return [conn for bucket in self._sessions.values() for conn in bucket]
