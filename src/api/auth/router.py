from typing import Annotated

from fastapi import APIRouter, Depends

from application.dependencies import get_user_service
from application.services.user_service import UserService
from core.dependencies import get_current_user_id
from protocol.rest.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> AuthResponse:
    return await service.register(body)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> AuthResponse:
    return await service.login(body)


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> MeResponse:
    return await service.get_me(user_id)
