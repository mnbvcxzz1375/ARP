from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message_id: str = Field(description="Stable message id used for delivery and ack.")
    task_id: str = Field(description="Task UUID.")
    type: str = Field(description="Protocol message type.")
    delivery_status: str = Field(description="Delivery status such as pending, delivered, or acked.")
    content: dict[str, Any] = Field(description="Persisted protocol message payload.")
    created_at: datetime = Field(description="Message creation time.")
    updated_at: datetime = Field(description="Last message update time.")

    model_config = dict(from_attributes=True)


class MessageListResponse(BaseModel):
    messages: list[MessageResponse] = Field(description="Messages in this page.")
    total: int = Field(description="Total matching messages.")
    offset: int = Field(description="Zero-based result offset.")
    limit: int = Field(description="Requested page size.")
