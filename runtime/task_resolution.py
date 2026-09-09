from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_task_v3 import TaskV3, validate_task_v3
from registries.goal_registry import GoalRegistry, GoalSpec
from registries.goal_resolver import (
    GoalResolution,
    GoalResolver,
    GoalResolverStatus,
)
from registries.handler_registry import (
    HandlerRegistry,
    HandlerSpec,
)
from registries.handler_resolver import (
    HandlerResolution,
    HandlerResolver,
    HandlerResolverStatus,
    HandlerRuntimeContext,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)
from registries.target_resolver import (
    TargetResolution,
    TargetResolver,
    TargetResolverStatus,
)


class TaskResolutionStatus(str, Enum):
    INVALID_TASK = "INVALID_TASK"

    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
    TARGET_INVALID = "TARGET_INVALID"

    GOAL_NOT_FOUND = "GOAL_NOT_FOUND"
    GOAL_VERSION_UNAVAILABLE = "GOAL_VERSION_UNAVAILABLE"
    GOAL_DISABLED = "GOAL_DISABLED"
    GOAL_INVALID = "GOAL_INVALID"

    HANDLER_NOT_FOUND = "HANDLER_NOT_FOUND"
    HANDLER_UNAVAILABLE = "HANDLER_UNAVAILABLE"
    HANDLER_AMBIGUOUS = "HANDLER_AMBIGUOUS"
    HANDLER_INVALID = "HANDLER_INVALID"

    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class TaskResolutionResult:
    """
    Complete runtime result of the current RESOLUTION phase.

    Current scope:
        - local TaskV3 validation;
        - Target resolution;
        - Goal resolution;
        - Handler resolution.

    Planning and execution are intentionally outside this layer.
    """

    status: TaskResolutionStatus
    task: TaskV3
    validation: object

    target_resolution: TargetResolution | None = None
    goal_resolution: GoalResolution | None = None
    handler_resolution: HandlerResolution | None = None

    target_record: TargetRecord | None = None
    goal_spec: GoalSpec | None = None
    handler_spec: HandlerSpec | None = None

    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is TaskResolutionStatus.RESOLVED


class TaskResolver:
    """
    Orchestrates the complete currently implemented RESOLUTION phase.

    Pipeline:

        TaskV3
          |
          v
        validate_task_v3()
          |
          +----------------------+----------------------+
          |                      |                      |
          v                      v                      v
        TargetResolver        GoalResolver        HandlerResolver
          |                      |                      |
          v                      v                      v
        TargetRecord           GoalSpec            HandlerSpec
          +----------------------+----------------------+
                                 |
                                 v
                       TaskResolutionResult

    Resolver responsibilities are independent:
        - TargetResolver resolves TaskTarget.
        - GoalResolver resolves TaskGoal.
        - HandlerResolver selects a compatible handler.

    This layer does not build an ExecutionPlan and does not execute anything.
    """

    def __init__(
        self,
        goal_registry: GoalRegistry,
        target_directory: TargetDirectory,
        handler_registry: HandlerRegistry,
    ) -> None:
        self._goal_resolver = GoalResolver(goal_registry)
        self._target_resolver = TargetResolver(target_directory)
        self._handler_resolver = HandlerResolver(handler_registry)

    @staticmethod
    def _validation_is_valid(validation_result: object) -> bool:
        issues = getattr(validation_result, "issues", None)

        if issues is None:
            raise AttributeError(
                "TaskValidationResult does not expose an 'issues' collection."
            )

        return len(issues) == 0

    @staticmethod
    def _map_target_status(
        target_resolution: TargetResolution,
    ) -> TaskResolutionStatus:
        if target_resolution.status is TargetResolverStatus.NOT_FOUND:
            return TaskResolutionStatus.TARGET_NOT_FOUND

        if target_resolution.status is TargetResolverStatus.AMBIGUOUS:
            return TaskResolutionStatus.TARGET_AMBIGUOUS

        if target_resolution.status is TargetResolverStatus.UNAVAILABLE:
            return TaskResolutionStatus.TARGET_UNAVAILABLE

        return TaskResolutionStatus.TARGET_INVALID

    @staticmethod
    def _map_goal_status(
        goal_resolution: GoalResolution,
    ) -> TaskResolutionStatus:
        if goal_resolution.status is GoalResolverStatus.NOT_FOUND:
            return TaskResolutionStatus.GOAL_NOT_FOUND

        if (
            goal_resolution.status
            is GoalResolverStatus.VERSION_UNAVAILABLE
        ):
            return TaskResolutionStatus.GOAL_VERSION_UNAVAILABLE

        if goal_resolution.status is GoalResolverStatus.DISABLED:
            return TaskResolutionStatus.GOAL_DISABLED

        return TaskResolutionStatus.GOAL_INVALID

    @staticmethod
    def _map_handler_status(
        handler_resolution: HandlerResolution,
    ) -> TaskResolutionStatus:
        if handler_resolution.status is HandlerResolverStatus.NOT_FOUND:
            return TaskResolutionStatus.HANDLER_NOT_FOUND

        if handler_resolution.status is HandlerResolverStatus.UNAVAILABLE:
            return TaskResolutionStatus.HANDLER_UNAVAILABLE

        if handler_resolution.status is HandlerResolverStatus.AMBIGUOUS:
            return TaskResolutionStatus.HANDLER_AMBIGUOUS

        return TaskResolutionStatus.HANDLER_INVALID

    def resolve(
        self,
        task: TaskV3,
        handler_context: HandlerRuntimeContext | None = None,
    ) -> TaskResolutionResult:
        validation_result = validate_task_v3(task)

        if not self._validation_is_valid(validation_result):
            return TaskResolutionResult(
                status=TaskResolutionStatus.INVALID_TASK,
                task=task,
                validation=validation_result,
                message="TaskV3 failed local semantic validation.",
            )

        target_resolution = self._target_resolver.resolve(
            task.intent.target
        )

        goal_resolution = self._goal_resolver.resolve(
            task.intent.goal
        )

        handler_resolution = self._handler_resolver.resolve(
            task,
            handler_context,
        )

        if not target_resolution.resolved:
            return TaskResolutionResult(
                status=self._map_target_status(target_resolution),
                task=task,
                validation=validation_result,
                target_resolution=target_resolution,
                goal_resolution=goal_resolution,
                handler_resolution=handler_resolution,
                target_record=target_resolution.record,
                goal_spec=goal_resolution.spec,
                handler_spec=handler_resolution.handler,
                message=target_resolution.message,
            )

        if not goal_resolution.resolved:
            return TaskResolutionResult(
                status=self._map_goal_status(goal_resolution),
                task=task,
                validation=validation_result,
                target_resolution=target_resolution,
                goal_resolution=goal_resolution,
                handler_resolution=handler_resolution,
                target_record=target_resolution.record,
                goal_spec=goal_resolution.spec,
                handler_spec=handler_resolution.handler,
                message=goal_resolution.message,
            )

        if not handler_resolution.resolved:
            return TaskResolutionResult(
                status=self._map_handler_status(handler_resolution),
                task=task,
                validation=validation_result,
                target_resolution=target_resolution,
                goal_resolution=goal_resolution,
                handler_resolution=handler_resolution,
                target_record=target_resolution.record,
                goal_spec=goal_resolution.spec,
                handler_spec=handler_resolution.handler,
                message=handler_resolution.message,
            )

        return TaskResolutionResult(
            status=TaskResolutionStatus.RESOLVED,
            task=task,
            validation=validation_result,
            target_resolution=target_resolution,
            goal_resolution=goal_resolution,
            handler_resolution=handler_resolution,
            target_record=target_resolution.record,
            goal_spec=goal_resolution.spec,
            handler_spec=handler_resolution.handler,
            message="",
        )