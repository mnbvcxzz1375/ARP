from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message_id: str
    task_id: str
    type: str
    delivery_status: str
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    offset: int
    limit: int
