from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.rating.constants import INITIAL_RATING


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str | None
    display_name: str
    created_at: datetime
    rating: int = INITIAL_RATING
    games_played: int = 0
    calibration_complete: bool = False
