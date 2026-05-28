from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    display_name: str
    password_hash: str
    created_at: datetime
