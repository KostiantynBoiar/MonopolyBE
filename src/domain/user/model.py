from datetime import datetime

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    display_name: str
    created_at: datetime
