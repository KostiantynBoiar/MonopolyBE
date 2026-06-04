from typing import Annotated

from fastapi import APIRouter, Depends, Query

from application.dependencies import get_user_service
from application.services.user_service import UserService
from protocol.rest.leaderboard import LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


# Public: the landing-page nav links here for logged-out visitors too.
@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    service: Annotated[UserService, Depends(get_user_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LeaderboardResponse:
    return await service.leaderboard(limit=limit, offset=offset)
