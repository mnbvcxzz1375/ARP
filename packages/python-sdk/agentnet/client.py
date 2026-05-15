"""REST client for the AgentNet API: agents, tasks, approvals."""

from __future__ import annotations

import os
from typing import Any

import httpx


class AgentNetError(Exception):
    """Raised when the API returns an error."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{code}] {message}")


class Client:
    """Synchronous REST client for the AgentNet Relay API.

    Usage:
        client = Client(base_url="http://localhost:8000", api_key="an_key_...")
        agent = client.create_agent(name="my-agent", runtime="python")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("AGENTNET_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("AGENTNET_API_KEY", "")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # factories
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "Client":
        """Create a Client from environment variables."""
        return cls()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _check(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.is_success:
            return resp.json()
        try:
            body = resp.json()
            err = body.get("error", {})
            raise AgentNetError(
                err.get("code", "UNKNOWN"),
                err.get("message", resp.text),
                status_code=resp.status_code,
            )
        except (ValueError, KeyError):
            raise AgentNetError("UNKNOWN", resp.text, status_code=resp.status_code)

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        return self._check(resp)

    def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._client.post(path, json=body or {})
        return self._check(resp)

    def _delete(self, path: str) -> None:
        resp = self._client.delete(path)
        if not resp.is_success:
            self._check(resp)

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # agents
    # ------------------------------------------------------------------

    def create_agent(
        self,
        name: str,
        runtime: str,
        *,
        description: str | None = None,
        capabilities: list[str] | None = None,
        inbound_policy: str = "request_approval",
        discoverable: bool = False,
    ) -> dict[str, Any]:
        """Create a new agent. Returns the agent dict including agent_token."""
        return self._post("/v1/agents", {
            "name": name,
            "runtime": runtime,
            "description": description,
            "capabilities": capabilities or [],
            "inbound_policy": inbound_policy,
            "discoverable": discoverable,
        })

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._get(f"/v1/agents/{agent_id}")

    def list_agents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        return self._get("/v1/agents", page=page, page_size=page_size, status=status, search=search)

    def rotate_token(self, agent_id: str) -> dict[str, Any]:
        return self._post(f"/v1/agents/{agent_id}/rotate-token")

    def delete_agent(self, agent_id: str) -> None:
        self._delete(f"/v1/agents/{agent_id}")

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------

    def create_task(
        self,
        assigned_to: str,
        *,
        from_agent_number: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._post("/v1/tasks", {
            "assigned_to": assigned_to,
            "from_agent_number": from_agent_number,
            "payload": payload or {},
            "idempotency_key": idempotency_key,
        })

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._get(f"/v1/tasks/{task_id}")

    def list_tasks(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        return self._get("/v1/tasks", status=status, offset=offset, limit=limit)

    def get_task_messages(
        self,
        task_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._get(f"/v1/tasks/{task_id}/messages", offset=offset, limit=limit)

    def get_task_progress(
        self,
        task_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._get(f"/v1/tasks/{task_id}/progress", offset=offset, limit=limit)

    # ------------------------------------------------------------------
    # approvals
    # ------------------------------------------------------------------

    def list_approvals(
        self,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        return self._get("/v1/approvals", status=status, offset=offset, limit=limit)

    def accept_approval(self, approval_id: str) -> dict[str, Any]:
        return self._post(f"/v1/approvals/{approval_id}/accept")

    def reject_approval(self, approval_id: str) -> dict[str, Any]:
        return self._post(f"/v1/approvals/{approval_id}/reject")

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
