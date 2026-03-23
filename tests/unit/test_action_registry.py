"""Tests for action registry."""

import pytest

from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.registry import ActionRegistry, register_action


class TestActionRegistry:
    def setup_method(self):
        ActionRegistry._actions.clear()

    def test_register_and_get(self):
        @register_action("test.action")
        class TestAction(BaseAction):
            name = "test.action"
            def run(self, context, params, executor, resolved_input=None):
                return ActionResult(status="done")

        action_cls = ActionRegistry.get("test.action")
        assert action_cls is TestAction

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="test.unknown"):
            ActionRegistry.get("test.unknown")

    def test_list_actions(self):
        @register_action("a.one")
        class A(BaseAction):
            name = "a.one"
            def run(self, context, params, executor, resolved_input=None):
                return ActionResult(status="done")

        @register_action("a.two")
        class B(BaseAction):
            name = "a.two"
            def run(self, context, params, executor, resolved_input=None):
                return ActionResult(status="done")

        names = ActionRegistry.list_actions()
        assert "a.one" in names
        assert "a.two" in names

    def test_duplicate_registration_raises(self):
        @register_action("dup.action")
        class First(BaseAction):
            name = "dup.action"
            def run(self, context, params, executor, resolved_input=None):
                return ActionResult(status="done")

        with pytest.raises(ValueError, match="already registered"):
            @register_action("dup.action")
            class Second(BaseAction):
                name = "dup.action"
                def run(self, context, params, executor, resolved_input=None):
                    return ActionResult(status="done")
