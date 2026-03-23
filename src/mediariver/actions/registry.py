"""Action name → class registry with decorator-based registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mediariver.actions.base import BaseAction


class ActionRegistry:
    _actions: dict[str, type[BaseAction]] = {}

    @classmethod
    def get(cls, name: str) -> type[BaseAction]:
        if name not in cls._actions:
            raise KeyError(f"Unknown action: '{name}'. Available: {list(cls._actions.keys())}")
        return cls._actions[name]

    @classmethod
    def register(cls, name: str, action_cls: type[BaseAction]) -> None:
        if name in cls._actions:
            raise ValueError(f"Action '{name}' is already registered")
        cls._actions[name] = action_cls

    @classmethod
    def list_actions(cls) -> list[str]:
        return list(cls._actions.keys())


def register_action(name: str):
    def decorator(cls):
        ActionRegistry.register(name, cls)
        return cls

    return decorator
