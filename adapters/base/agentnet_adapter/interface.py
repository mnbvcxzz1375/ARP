from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterContext:
    task_id: str
    agent_number: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AdapterInterface:
    async def start(self) -> None:
        raise NotImplementedError("AdapterInterface.start must be implemented by adapters.")

    async def stop(self) -> None:
        raise NotImplementedError("AdapterInterface.stop must be implemented by adapters.")

    async def handle_task(self, context: AdapterContext, content: list[dict[str, Any]]) -> dict[str, Any] | None:
        raise NotImplementedError("AdapterInterface.handle_task must be implemented by adapters.")

