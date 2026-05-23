"""CircuitBreaker model: implements circuit breaker pattern for relay nodes."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CircuitBreaker(Base):
    __tablename__ = "circuit_breakers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    relay_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relay_nodes.id"), nullable=False, unique=True, index=True
    )
    # One circuit breaker per relay node

    state: Mapped[str] = mapped_column(String(16), default="closed", nullable=False, index=True)
    # States: closed (normal), open (failing), half_open (testing recovery)

    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Consecutive failures in current window

    last_failure_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # When state=open, circuit stays open until this time

    success_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    # Consecutive successes needed to close from half_open

    failure_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # Consecutive failures to trip circuit from closed to open

    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Consecutive successes in half_open state

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    relay_node: Mapped["RelayNode"] = relationship(lazy="select")

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (relay should be avoided)."""
        if self.state == "open":
            if self.open_until and datetime.now(datetime.now().astimezone().tzinfo) < self.open_until:
                return True
            # Circuit should transition to half_open
            return False
        return False

    @property
    def should_allow_request(self) -> bool:
        """Check if requests should be allowed through this circuit."""
        if self.state == "closed":
            return True
        if self.state == "half_open":
            return True  # Allow limited requests to test recovery
        if self.state == "open":
            return not self.is_open  # Allow if open period expired
        return False
