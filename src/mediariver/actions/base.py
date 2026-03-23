"""Base action class and result type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from mediariver.actions.executor import CommandExecutor


@dataclass
class ActionResult:
    """Result returned by an action's run() method."""

    status: str  # "done" | "failed" | "skipped"
    output: str | None = None
    duration_ms: int = 0
    extras: dict[str, Any] = field(default_factory=dict)


class EmptyParams(BaseModel):
    """Default params model for actions that take no params."""


class BaseAction(ABC):
    """Abstract base class for all actions."""

    name: str
    params_model: type[BaseModel] = EmptyParams

    @abstractmethod
    def run(
        self,
        context: dict[str, Any],
        params: BaseModel,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        ...
