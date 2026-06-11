from __future__ import annotations

from datetime import UTC, datetime

from domain.game.enums import GameMode
from infra.mongo.sessions.mapper import document_from_mongo, to_domain


def test_legacy_session_document_defaults_to_normal_game_mode() -> None:
    raw = {
        "_id": "session-1",
        "invite_code": "TYC-TEST",
        "host_user_id": "user-1",
        "status": "waiting",
        "visibility": "public",
        "ranked": True,
        "members": [
            {
                "user_id": "user-1",
                "display_name": "Host",
                "role": "host",
                "joined_at": datetime(2026, 6, 11, tzinfo=UTC),
            }
        ],
        "created_at": datetime(2026, 6, 11, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 11, tzinfo=UTC),
    }

    session = to_domain(document_from_mongo(raw))

    assert session.game_mode == GameMode.NORMAL
    assert session.max_players == 8
