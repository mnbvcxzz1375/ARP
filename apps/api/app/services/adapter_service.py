"""Adapter orchestration service.

Dispatches tasks to registered adapters and injects egress gateway
context so that adapters route external requests through the platform
egress policy enforcement layer.
"""

from __future__ import annotations

import hashlib
import json
import importlib
import logging
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentnet_adapter.interface import AdapterContext
from app.config import get_settings
from app.models.agent import Agent
from app.models.egress_gateway import EgressGateway
from app.protocol.constants import ErrorCode
from app.exceptions import DomainException

logger = logging.getLogger(__name__)

_ADAPTER_REGISTRY: dict[str, Any] = {}


def _registry_key(adapter_type: str, config: dict[str, Any] | BaseModel | None) -> str:
    """Build a deterministic registry key that includes config so different
    configs are not served from the same cached instance.
    """
    if config is None:
        return adapter_type + ":no_config"
    if isinstance(config, BaseModel):
        raw = config.model_dump_json()
    else:
        raw = json.dumps(config, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{adapter_type}:{digest}"


def _get_adapter(adapter_type: str, config: dict[str, Any] | BaseModel | None = None):
    """Lazy-load and cache adapter instances by type name + config hash.

    Dict config is validated and converted to the adapter's Pydantic
    AdapterConfig before instantiation.  If config is None, fail closed —
    production paths must never construct a default runnable config implicitly.
    """
    key = _registry_key(adapter_type, config)
    if key in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[key]

    adapter_map = {
        "openclaw": ("agentnet_openclaw.adapter", "OpenClawAdapter", "agentnet_openclaw.config", "AdapterConfig"),
    }

    entry = adapter_map.get(adapter_type)
    if entry is None:
        raise DomainException(
            ErrorCode.ADAPTER_NOT_FOUND,
            f"Unknown adapter type: {adapter_type}",
            status_code=400,
        )

    module_name, class_name, config_module_name, config_class_name = entry
    module = importlib.import_module(module_name)
    adapter_cls = getattr(module, class_name)

    if config is None:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Adapter {adapter_type} requires explicit adapter_config — "
            f"no implicit default config is permitted in production. "
            f"Pass adapter_config explicitly or configure a source.",
            status_code=400,
        )

    # If config is a plain dict, validate and convert to AdapterConfig
    if isinstance(config, dict):
        config_module = importlib.import_module(config_module_name)
        config_cls = getattr(config_module, config_class_name)
        try:
            config = config_cls.model_validate(config)
        except ValidationError as exc:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                f"Invalid adapter config for {adapter_type}: {exc}",
                status_code=400,
            ) from exc

    instance = adapter_cls(config)
    _ADAPTER_REGISTRY[key] = instance
    return instance


async def dispatch_task(
    session: AsyncSession,
    *,
    task_id: str,
    agent_id: str,
    adapter_type: str,
    content: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    adapter_config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Dispatch a task to the appropriate adapter with egress context.

    Looks up the agent's egress gateway (if configured) and injects
    a make_external_request callback into the AdapterContext so the
    adapter can only make external calls through the egress policy
    enforcement layer.
    """
    # Fail closed: task_uuid and agent_uuid must exist in metadata
    # before we construct the AdapterContext that passes them to egress.
    _metadata = metadata or {}
    task_uuid = _metadata.get("task_uuid")
    agent_uuid = _metadata.get("agent_uuid")
    if not task_uuid:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "dispatch_task requires metadata.task_uuid — cannot dispatch without task context",
            status_code=400,
        )
    if not agent_uuid:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "dispatch_task requires metadata.agent_uuid — cannot dispatch without agent identity",
            status_code=400,
        )

    adapter = _get_adapter(adapter_type, config=adapter_config)

    # Look up the agent to find its egress gateway assignment.
    agent_result = await session.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()

    egress_gateway_id: str | None = None
    make_external_request = None

    if agent is not None and agent.egress_gateway_id is not None:
        gw_result = await session.execute(
            select(EgressGateway).where(
                EgressGateway.id == agent.egress_gateway_id,
                EgressGateway.enabled.is_(True),
            )
        )
        gw = gw_result.scalar_one_or_none()
        if gw is not None:
            egress_gateway_id = str(gw.id)
            # Inject the egress proxy callback.  The adapter must use
            # context.external_request() which calls this function --
            # direct httpx/aiohttp calls bypass egress policy.
            from app.services.egress_service import proxy_external_request

            async def _make_request(**kwargs: Any) -> dict[str, Any]:
                return await proxy_external_request(session, **kwargs)

            make_external_request = _make_request

    context = AdapterContext(
        task_id=task_id,
        agent_number=agent.agent_number if agent else "UNKNOWN",
        metadata=_metadata,
        egress_gateway_id=egress_gateway_id,
        make_external_request=make_external_request,
    )

    try:
        result = await adapter.handle_task(context, content)
    except DomainException:
        raise
    except Exception as exc:
        logger.exception("Adapter %s failed for task %s", adapter_type, task_id)
        raise DomainException(
            ErrorCode.ADAPTER_EXECUTION_FAILED,
            f"Adapter execution failed: {exc}",
            status_code=500,
        ) from exc

    return result


async def start_adapter(
    adapter_type: str,
    adapter_config: dict[str, Any] | BaseModel,
) -> None:
    """Start a registered adapter. Requires explicit config — no implicit defaults."""
    adapter = _get_adapter(adapter_type, config=adapter_config)
    await adapter.start()
    logger.info("Adapter %s started", adapter_type)


async def stop_adapter(
    adapter_type: str,
    adapter_config: dict[str, Any] | BaseModel,
) -> None:
    """Stop a registered adapter. Requires explicit config — no implicit defaults."""
    adapter = _get_adapter(adapter_type, config=adapter_config)
    await adapter.stop()
    logger.info("Adapter %s stopped", adapter_type)