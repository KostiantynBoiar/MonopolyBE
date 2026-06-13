from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from application.dependencies import get_telegram_auth_service, get_user_service
from application.services.telegram_auth_service import TelegramAuthService
from application.services.user_service import UserService
from core.dependencies import get_current_user_id
from protocol.rest.auth import (
    AuthResponse,
    LinkEmailRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TelegramExchangeRequest,
    TelegramStartResponse,
)

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


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    body: RefreshRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> AuthResponse:
    return await service.refresh(body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    await service.logout(body.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> MeResponse:
    return await service.get_me(user_id)


# ---------------------------------------------------------------------------
# Telegram OIDC
# ---------------------------------------------------------------------------


@router.get("/telegram/start", response_model=TelegramStartResponse)
async def telegram_start(
    service: Annotated[TelegramAuthService, Depends(get_telegram_auth_service)],
) -> TelegramStartResponse:
    url = await service.start()
    return TelegramStartResponse(url=url)


@router.get("/telegram/callback")
async def telegram_callback(
    code: str,
    state: str,
    service: Annotated[TelegramAuthService, Depends(get_telegram_auth_service)],
) -> RedirectResponse:
    redirect_url = await service.handle_callback(code=code, state=state)
    return RedirectResponse(url=redirect_url)


@router.post("/telegram/exchange", response_model=AuthResponse)
async def telegram_exchange(
    body: TelegramExchangeRequest,
    service: Annotated[TelegramAuthService, Depends(get_telegram_auth_service)],
) -> AuthResponse:
    return await service.exchange(body.code)


@router.get("/telegram/connect/start", response_model=TelegramStartResponse)
async def telegram_connect_start(
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[TelegramAuthService, Depends(get_telegram_auth_service)],
) -> TelegramStartResponse:
    url = await service.start_connect(user_id)
    return TelegramStartResponse(url=url)


@router.post("/link/email", response_model=MeResponse)
async def link_email(
    body: LinkEmailRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> MeResponse:
    return await service.link_email(user_id, body)
