"""Pydantic schemas for routing runtime models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# RouteDecision schemas
class RouteDecisionResponse(BaseModel):
    id: str = Field(description="Route decision UUID.")
    task_id: str = Field(description="Task UUID.")
    message_id: str = Field(description="Message ID.")
    trace_id: str | None = Field(description="Trace ID for distributed tracing.")
    selected_route_type: str = Field(description="Selected route type.")
    selected_relay_node_id: str | None = Field(description="Selected relay node UUID.")
    candidate_routes: list[dict[str, Any]] = Field(description="Candidate routes considered.")
    rejection_reasons: dict[str, Any] = Field(description="Rejection reasons for filtered routes.")
    fallback_from_route: str | None = Field(description="Route that was fallen back from.")
    fallback_reason: str | None = Field(description="Reason for fallback.")
    timeliness_mode: str = Field(description="Timeliness mode (realtime, interactive, normal, batch, durable).")
    risk_level: str | None = Field(description="Risk level assessment.")
    final_score: float | None = Field(description="Final route score.")
    decision_time_ms: int | None = Field(description="Decision computation time in milliseconds.")
    shadow_mode: bool = Field(description="Whether this decision was made in shadow mode.")
    created_at: datetime = Field(description="Decision creation time.")

    model_config = dict(from_attributes=True)


class RouteDecisionListResponse(BaseModel):
    decisions: list[RouteDecisionResponse] = Field(description="Route decisions in this page.")
    total: int = Field(description="Total matching route decisions.")
    offset: int = Field(description="Zero-based result offset.")
    limit: int = Field(description="Requested page size.")


# RouteLease schemas
class RouteLeaseResponse(BaseModel):
    id: str = Field(description="Route lease UUID.")
    source_agent_id: str = Field(description="Source agent UUID.")
    target_agent_id: str = Field(description="Target agent UUID.")
    route_type: str = Field(description="Route type.")
    expires_at: datetime = Field(description="Lease expiration time.")
    max_messages: int | None = Field(description="Maximum messages allowed.")
    max_bytes: int | None = Field(description="Maximum bytes allowed.")
    allowed_task_types: list[str] | None = Field(description="Allowed task types.")
    messages_sent: int = Field(description="Messages sent so far.")
    bytes_sent: int = Field(description="Bytes sent so far.")
    approval_id: str | None = Field(description="Linked approval UUID.")
    revoked_at: datetime | None = Field(description="Revocation time.")
    revoke_reason: str | None = Field(description="Revocation reason.")
    created_at: datetime = Field(description="Lease creation time.")
    updated_at: datetime = Field(description="Last lease update time.")

    model_config = dict(from_attributes=True)


class RouteLeaseListResponse(BaseModel):
    leases: list[RouteLeaseResponse] = Field(description="Route leases in this page.")
    total: int = Field(description="Total matching route leases.")
    offset: int = Field(description="Zero-based result offset.")
    limit: int = Field(description="Requested page size.")


# MessageDeliveryEvent schemas
class MessageDeliveryEventResponse(BaseModel):
    id: str = Field(description="Delivery event UUID.")
    message_id: str = Field(description="Message ID.")
    task_id: str = Field(description="Task UUID.")
    event_type: str = Field(description="Event type (queued, route_selected, delivering, delivered, acknowledged, delivery_failed, expired).")
    route_type: str | None = Field(description="Route type used.")
    relay_node_id: str | None = Field(description="Relay node UUID.")
    latency_ms: int | None = Field(description="Latency in milliseconds.")
    queue_wait_ms: int | None = Field(description="Queue wait time in milliseconds.")
    error_code: str | None = Field(description="Error code if failed.")
    error_message: str | None = Field(description="Error message if failed.")
    extra_metadata: dict[str, Any] = Field(description="Additional metadata.", alias="metadata")
    created_at: datetime = Field(description="Event creation time.")

    model_config = dict(from_attributes=True, populate_by_name=True)


class MessageDeliveryEventListResponse(BaseModel):
    events: list[MessageDeliveryEventResponse] = Field(description="Delivery events in this page.")
    total: int = Field(description="Total matching delivery events.")


# RelayNode schemas
class RegisterRelayNodeRequest(BaseModel):
    node_name: str = Field(..., max_length=128, description="Unique relay node name.")
    node_type: str = Field(..., description="Node type (central, personal_edge, local_edge, regional, egress, dedicated).")
    region: str | None = Field(default=None, max_length=64, description="Network region.")
    zone: str | None = Field(default=None, max_length=64, description="Network zone.")
    capabilities: list[str] = Field(default_factory=list, description="Node capabilities.")
    max_capacity: int | None = Field(default=None, description="Maximum capacity.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata.")


class RelayNodeHeartbeatRequest(BaseModel):
    current_load: float = Field(..., ge=0.0, le=1.0, description="Current load (0.0 to 1.0).")
    queue_depth: int = Field(..., ge=0, description="Current queue depth.")
    avg_latency_ms: float | None = Field(default=None, description="Average latency in milliseconds.")
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0, description="Success rate (0.0 to 1.0).")


class RelayNodeResponse(BaseModel):
    id: str = Field(description="Relay node UUID.")
    node_name: str = Field(description="Relay node name.")
    node_type: str = Field(description="Node type.")
    status: str = Field(description="Health status (healthy, degraded, down, unknown).")
    current_load: float = Field(description="Current load.")
    queue_depth: int = Field(description="Current queue depth.")
    avg_latency_ms: float | None = Field(description="Average latency in milliseconds.")
    success_rate: float | None = Field(description="Success rate.")
    capabilities: list[str] = Field(description="Node capabilities.")
    max_capacity: int | None = Field(description="Maximum capacity.")
    region: str | None = Field(description="Network region.")
    zone: str | None = Field(description="Network zone.")
    last_heartbeat_at: datetime | None = Field(description="Last heartbeat time.")
    extra_metadata: dict[str, Any] = Field(description="Additional metadata.", alias="metadata")
    enabled: bool = Field(description="Whether the node is enabled.")
    created_at: datetime = Field(description="Node creation time.")
    updated_at: datetime = Field(description="Last node update time.")

    model_config = dict(from_attributes=True, populate_by_name=True)


class RelayNodeListResponse(BaseModel):
    nodes: list[RelayNodeResponse] = Field(description="Relay nodes in this page.")
    total: int = Field(description="Total matching relay nodes.")
    offset: int = Field(description="Zero-based result offset.")
    limit: int = Field(description="Requested page size.")


# RouteMetricEvent schemas
class RouteMetricEventResponse(BaseModel):
    id: str = Field(description="Metric event UUID.")
    task_id: str | None = Field(description="Task UUID.")
    message_id: str | None = Field(description="Message ID.")
    route_type: str = Field(description="Route type.")
    relay_node_id: str | None = Field(description="Relay node UUID.")
    latency_ms: int | None = Field(description="Latency in milliseconds.")
    queue_wait_ms: int | None = Field(description="Queue wait time in milliseconds.")
    delivery_attempts: int = Field(description="Number of delivery attempts.")
    fallback_count: int = Field(description="Number of fallbacks.")
    error_code: str | None = Field(description="Error code if failed.")
    policy_denied: bool = Field(description="Whether denied by policy.")
    egress_bytes: int | None = Field(description="Egress bytes.")
    extra_metadata: dict[str, Any] = Field(description="Additional metadata.", alias="metadata")
    created_at: datetime = Field(description="Event creation time.")

    model_config = dict(from_attributes=True, populate_by_name=True)


class RouteMetricEventListResponse(BaseModel):
    events: list[RouteMetricEventResponse] = Field(description="Metric events in this page.")
    total: int = Field(description="Total matching metric events.")
