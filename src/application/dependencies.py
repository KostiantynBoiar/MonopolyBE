from typing import Annotated

from fastapi import Depends, Request

from application.services.game_service import GameService
from application.services.session_service import SessionService
from application.services.user_service import UserService
from core.config import Settings, get_settings


def get_user_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserService:
    return UserService.from_db(request.app.state.mongo.db, settings)


def get_session_service(request: Request) -> SessionService:
    return SessionService.from_db(request.app.state.mongo.db)


def get_game_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> GameService:
    return GameService.from_db(request.app.state.mongo.db, settings)
