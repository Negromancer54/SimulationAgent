from __future__ import annotations

from agent_task_v3 import GoalKind, TaskOperation
from registries.goal_registry import GoalRegistry
from registries.handler_registry import HandlerRegistry
from runtime.v3_registry import (
    FILE_WRITE_GOAL_ID,
    FILE_WRITE_GOAL_VERSION,
    FILE_WRITE_HANDLER_ID,
    register_v3_defaults,
)


def test_register_v3_defaults_registers_file_write_goal() -> None:
    goal_registry = GoalRegistry()
    handler_registry = HandlerRegistry()

    register_v3_defaults(
        goal_registry,
        handler_registry,
    )

    result = goal_registry.resolve(
        FILE_WRITE_GOAL_ID,
        FILE_WRITE_GOAL_VERSION,
    )

    assert result.status.value == "FOUND"
    assert result.spec is not None
    assert result.spec.identifier == FILE_WRITE_GOAL_ID
    assert result.spec.version == FILE_WRITE_GOAL_VERSION
    assert result.spec.kind is GoalKind.OUTCOME


def test_register_v3_defaults_registers_file_write_handler() -> None:
    goal_registry = GoalRegistry()
    handler_registry = HandlerRegistry()

    register_v3_defaults(
        goal_registry,
        handler_registry,
    )

    assert handler_registry.contains(
        FILE_WRITE_HANDLER_ID
    )

    handler = handler_registry.get(
        FILE_WRITE_HANDLER_ID
    )

    assert handler is not None
    assert handler.handler_id == FILE_WRITE_HANDLER_ID
    assert handler.goal_identifier == FILE_WRITE_GOAL_ID
    assert handler.goal_version == FILE_WRITE_GOAL_VERSION
    assert handler.applicability.operations == (
        TaskOperation.CHANGE,
    )
    assert handler.required_capabilities == (
        "filesystem.write",
    )


def test_register_v3_defaults_registers_matching_goal_and_handler() -> None:
    goal_registry = GoalRegistry()
    handler_registry = HandlerRegistry()

    register_v3_defaults(
        goal_registry,
        handler_registry,
    )

    handlers = handler_registry.list_for_goal(
        FILE_WRITE_GOAL_ID,
        FILE_WRITE_GOAL_VERSION,
    )

    assert len(handlers) == 1
    assert handlers[0].handler_id == FILE_WRITE_HANDLER_ID
