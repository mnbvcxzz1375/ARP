"""Phase 12: Routing Runtime Foundation (Shadow Mode).

Revision ID: 0012_phase12_routing_foundation
Revises: 0011_add_agent_token_rotated_at
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_phase12_routing_foundation"
down_revision: Union[str, None] = "0011_add_agent_token_rotated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create relay_nodes table
    op.create_table(
        "relay_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("node_name", sa.String(128), nullable=False, unique=True),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("current_load", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("queue_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("max_capacity", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("zone", sa.String(64), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relay_nodes_node_name", "relay_nodes", ["node_name"])
    op.create_index("ix_relay_nodes_node_type", "relay_nodes", ["node_type"])

    # Create route_decisions table
    op.create_table(
        "route_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("selected_route_type", sa.String(32), nullable=False),
        sa.Column("selected_relay_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_routes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("rejection_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("fallback_from_route", sa.String(32), nullable=True),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("timeliness_mode", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("decision_time_ms", sa.Integer(), nullable=True),
        sa.Column("shadow_mode", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_relay_node_id"], ["relay_nodes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_route_decisions_task_id", "route_decisions", ["task_id"])
    op.create_index("ix_route_decisions_message_id", "route_decisions", ["message_id"])
    op.create_index("ix_route_decisions_trace_id", "route_decisions", ["trace_id"])

    # Create route_leases table
    op.create_table(
        "route_leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_type", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_messages", sa.Integer(), nullable=True),
        sa.Column("max_bytes", sa.BigInteger(), nullable=True),
        sa.Column("allowed_task_types", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("messages_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_sent", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_route_leases_source_agent_id", "route_leases", ["source_agent_id"])
    op.create_index("ix_route_leases_target_agent_id", "route_leases", ["target_agent_id"])
    op.create_index("ix_route_leases_expires_at", "route_leases", ["expires_at"])

    # Create message_delivery_events table
    op.create_table(
        "message_delivery_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("route_type", sa.String(32), nullable=True),
        sa.Column("relay_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relay_node_id"], ["relay_nodes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_message_delivery_events_message_id", "message_delivery_events", ["message_id"])
    op.create_index("ix_message_delivery_events_task_id", "message_delivery_events", ["task_id"])
    op.create_index("ix_message_delivery_events_event_type", "message_delivery_events", ["event_type"])
    op.create_index("ix_message_delivery_events_created_at", "message_delivery_events", ["created_at"])

    # Create route_metric_events table
    op.create_table(
        "route_metric_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", sa.String(64), nullable=True),
        sa.Column("route_type", sa.String(32), nullable=False),
        sa.Column("relay_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fallback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("policy_denied", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("egress_bytes", sa.BigInteger(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relay_node_id"], ["relay_nodes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_route_metric_events_task_id", "route_metric_events", ["task_id"])
    op.create_index("ix_route_metric_events_message_id", "route_metric_events", ["message_id"])
    op.create_index("ix_route_metric_events_route_type", "route_metric_events", ["route_type"])
    op.create_index("ix_route_metric_events_relay_node_id", "route_metric_events", ["relay_node_id"])
    op.create_index("ix_route_metric_events_error_code", "route_metric_events", ["error_code"])
    op.create_index("ix_route_metric_events_created_at", "route_metric_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("route_metric_events")
    op.drop_table("message_delivery_events")
    op.drop_table("route_leases")
    op.drop_table("route_decisions")
    op.drop_table("relay_nodes")
