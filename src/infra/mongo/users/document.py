from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.rating.constants import INITIAL_RATING


class UserDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    display_name: str
    password_hash: str
    created_at: datetime
    rating: int = INITIAL_RATING
    games_played: int = 0
    calibration_complete: bool = False
