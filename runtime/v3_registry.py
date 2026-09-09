from __future__ import annotations

from registries.goal_registry import GoalRegistry, GoalSpec
from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
)
from agent_task_v3 import GoalKind, TaskOperation


FILE_WRITE_GOAL_ID = "file.write"
FILE_WRITE_GOAL_VERSION = 1
FILE_WRITE_HANDLER_ID = "file.write.handler"


def register_v3_goals(
    registry: GoalRegistry,
) -> None:
    registry.register(
        GoalSpec(
            identifier=FILE_WRITE_GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=FILE_WRITE_GOAL_VERSION,
            parameter_schema={
                "type": "object",
                "required": (
                    "path",
                    "content",
                ),
                "properties": {
                    "path": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "content": {
                        "type": "string",
                    },
                },
            },
            semantic_contract=(
                "Write the specified UTF-8 text content "
                "to a file inside the SimulationZero-Cpp project."
            ),
            owner="PROJECT",
        )
    )


def register_v3_handlers(
    registry: HandlerRegistry,
) -> None:
    registry.register(
        HandlerSpec(
            handler_id=FILE_WRITE_HANDLER_ID,
            goal_identifier=FILE_WRITE_GOAL_ID,
            goal_version=FILE_WRITE_GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,),
            ),
            required_capabilities=(
                "filesystem.write",
            ),
            owner="PROJECT",
        )
    )


def register_v3_defaults(
    goal_registry: GoalRegistry,
    handler_registry: HandlerRegistry,
) -> None:
    register_v3_goals(goal_registry)
    register_v3_handlers(handler_registry)