"""Agent adapter base interface and context.

Adapters implement AdapterInterface to handle tasks from the relay platform.
Production adapters that need external HTTP/API access MUST use
AdapterContext.make_external_request() -- direct outbound calls bypass
egress policy enforcement and are considered a contract violation.

Default-deny guard: with no egress gateway bound, external_request()
fails closed (RuntimeError) — the agent cannot reach any external host.
With a gateway bound, every request passes the egress policy decision
point: http/https only, target host rejected if loopback/private/
reserved/link-local or inside the scope's network_cidr unless the
gateway was explicitly registered with allow_internal_egress=True.

Honest coverage marking: this guard protects only the permitted path
(egress_service.proxy_external_request). Coverage gaps that remain and
are NOT protected by it in this round:
  * direct ``import httpx`` / aiohttp / requests usage inside adapter
    code or the API server itself — network-layer defence in depth
    (post-milestone) is required to close this;
  * stdio-type adapter child processes that make their own outbound
    connections (e.g. an MCP stdio server spawning a subprocess);
  * DNS names are not resolved by the host policy — a name that does
    not parse as an IP literal is treated as non-internal, so
    DNS-rebinding style targets need network-layer controls too.

The host-validation utility itself (egress_service.validate_host_not_
internal) is reused by the MCP adapter to validate HTTP-type MCP server
addresses — that is its only live consumer this round.

Security note: this is a *cooperative* contract at the application
layer.  For defence-in-depth, production deployments should additionally
enforce network-level egress restrictions (e.g. Kubernetes network
policies, firewall rules, or service mesh egress gateways) so that
even a misbehaving adapter subprocess cannot bypass the proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


# Type alias for the egress proxy callback provided by the platform.
# Signature matches egress_service.proxy_external_request keyword args.
EgressProxyFn = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


@dataclass(frozen=True)
class AdapterContext:
    """Context passed to adapter.handle_task() for each inbound task.

    Attributes:
        task_id: UUID of the task being processed.
        agent_number: Non-enumerable Agent Number of the target agent.
        metadata: Arbitrary metadata attached to the task routing decision.
        egress_gateway_id: UUID of the egress gateway this adapter must
            route external requests through.  None means no egress gateway
            is configured; external access is not permitted.
        make_external_request: Platform-provided callback that enforces
            egress policy (domain allowlist, secret injection, rate limit,
            cache, high-risk approval, audit).  Adapters MUST call this
            instead of using httpx/aiohttp/requests directly.
    """

    task_id: str
    agent_number: str
    metadata: dict[str, Any] = field(default_factory=dict)
    egress_gateway_id: str | None = None
    make_external_request: EgressProxyFn | None = None

    async def external_request(
        self,
        *,
        request_type: str,
        target_url: str,
        request_body: dict | None = None,
        headers: dict | None = None,
    ) -> dict[str, Any]:
        """Send an external HTTP request through the egress gateway.

        This is the ONLY approved way for adapters to access external
        services.  It enforces domain allowlist, secret injection, rate
        limiting, caching, and high-risk approval.

        Raises:
            RuntimeError: If no egress gateway is configured or if
                metadata is missing task_uuid/agent_uuid (fail closed).
        """
        if self.make_external_request is None or self.egress_gateway_id is None:
            raise RuntimeError(
                "External request rejected: no egress gateway configured for this adapter. "
                "Configure an egress gateway or restrict this adapter to local-only execution."
            )
        task_uuid = self.metadata.get("task_uuid")
        agent_uuid = self.metadata.get("agent_uuid")
        if not task_uuid or not agent_uuid:
            raise RuntimeError(
                "External request rejected: metadata must contain task_uuid and agent_uuid "
                "for egress audit and policy enforcement. "
                f"Got task_uuid={task_uuid!r}, agent_uuid={agent_uuid!r}."
            )
        return await self.make_external_request(
            gateway_id=self.egress_gateway_id,
            task_id=task_uuid,
            agent_id=agent_uuid,
            request_type=request_type,
            target_url=target_url,
            request_body=request_body,
            headers=headers,
        )


class AdapterInterface:
    """Base class for all AgentNet adapters.

    Subclass and implement start(), stop(), and handle_task().
    """

    async def start(self) -> None:
        raise NotImplementedError("AdapterInterface.start must be implemented by adapters.")

    async def stop(self) -> None:
        raise NotImplementedError("AdapterInterface.stop must be implemented by adapters.")

    async def handle_task(self, context: AdapterContext, content: list[dict[str, Any]]) -> dict[str, Any] | None:
        raise NotImplementedError("AdapterInterface.handle_task must be implemented by adapters.")