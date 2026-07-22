from __future__ import annotations

from typing import Any


class EnvAdapter:
    """Small compatibility wrapper around the competition environment."""

    def __init__(self, env: Any, *, max_tool_hops: int = 8) -> None:
        self.env = env
        self.max_tool_hops = int(max_tool_hops)

    def reset(self) -> Any:
        return self.env.reset()

    def interact(self, message: str) -> Any:
        try:
            return self.env.interact(message, max_tool_hops=self.max_tool_hops)
        except TypeError:
            return self.env.interact(message)

    def snapshot(self) -> Any:
        return self.env.snapshot()

    def restore(self, snapshot: Any) -> None:
        self.env.restore(snapshot)

    def trace(self) -> dict[str, Any]:
        value = self.env.export_trace_dict()
        return value if isinstance(value, dict) else {}
