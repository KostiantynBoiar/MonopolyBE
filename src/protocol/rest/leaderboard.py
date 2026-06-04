from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    display_name: str
    rating: int
    games_played: int
    calibration_complete: bool


class LeaderboardResponse(BaseModel):
    items: list[LeaderboardEntry]
