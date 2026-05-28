from typing import Annotated

from fastapi import Depends, Request

from application.services.user_service import UserService
from core.config import Settings, get_settings


def get_user_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserService:
    return UserService.from_db(request.app.state.mongo.db, settings)
