from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuthIdentityDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    provider: str
    provider_user_id: str
    username: str | None
    picture_url: str | None
    created_at: datetime
    updated_at: datetime
