from __future__ import annotations

from dataclasses import dataclass

from agent_task_v3 import TaskGoal
from registries.goal_registry import (
    GoalRegistry,
    GoalResolutionStatus,
    GoalSpec,
)


class GoalResolverStatus(str):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    VERSION_UNAVAILABLE = "VERSION_UNAVAILABLE"
    DISABLED = "DISABLED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class GoalResolution:
    status: str
    goal: TaskGoal
    spec: GoalSpec | None = None
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == GoalResolverStatus.RESOLVED


class GoalResolver:
    """
    Resolves a TaskGoal against a GoalRegistry.

    Responsibilities:
        - validate the minimal addressability of TaskGoal;
        - ask GoalRegistry for the exact requested GoalSpec;
        - translate registry resolution into a runtime resolution result.

    Non-responsibilities:
        - validating goal parameters against parameter schemas;
        - selecting handlers;
        - checking preconditions;
        - planning;
        - executing goals.
    """

    def __init__(self, registry: GoalRegistry) -> None:
        self._registry = registry

    @staticmethod
    def _validate_goal(goal: TaskGoal) -> str | None:
        if not isinstance(goal, TaskGoal):
            return "GoalResolver accepts only TaskGoal instances."

        if (
            not isinstance(goal.identifier, str)
            or not goal.identifier.strip()
        ):
            return "TaskGoal.identifier must be a non-empty string."

        if (
            not isinstance(goal.version, int)
            or isinstance(goal.version, bool)
            or goal.version <= 0
        ):
            return "TaskGoal.version must be a positive integer."

        if not isinstance(goal.parameters, dict):
            return "TaskGoal.parameters must be a dictionary."

        return None

    def resolve(self, goal: TaskGoal) -> GoalResolution:
        validation_error = self._validate_goal(goal)

        if validation_error is not None:
            return GoalResolution(
                status=GoalResolverStatus.INVALID,
                goal=goal,
                message=validation_error,
            )

        registry_result = self._registry.resolve(
            goal.identifier,
            goal.version,
        )

        if registry_result.status is GoalResolutionStatus.FOUND:
            return GoalResolution(
                status=GoalResolverStatus.RESOLVED,
                goal=goal,
                spec=registry_result.spec,
                message="",
            )

        if registry_result.status is GoalResolutionStatus.NOT_FOUND:
            return GoalResolution(
                status=GoalResolverStatus.NOT_FOUND,
                goal=goal,
                message=registry_result.message,
            )

        if (
            registry_result.status
            is GoalResolutionStatus.VERSION_UNAVAILABLE
        ):
            return GoalResolution(
                status=GoalResolverStatus.VERSION_UNAVAILABLE,
                goal=goal,
                message=registry_result.message,
            )

        if registry_result.status is GoalResolutionStatus.DISABLED:
            return GoalResolution(
                status=GoalResolverStatus.DISABLED,
                goal=goal,
                spec=registry_result.spec,
                message=registry_result.message,
            )

        return GoalResolution(
            status=GoalResolverStatus.INVALID,
            goal=goal,
            message=(
                "GoalRegistry returned an unsupported "
                "resolution status."
            ),
        )