from __future__ import annotations

from agent_task_v3 import TaskV3

from runtime.assertions import AssertionRegistry
from registries.goal_registry import GoalRegistry
from registries.handler_registry import HandlerRegistry
from registries.handler_resolver import HandlerRuntimeContext
from registries.target_directory import TargetDirectory
from runtime.cancellation import CancellationToken
from runtime.preconditions import (
    Precondition,
    PreconditionEvaluator,
    PreconditionRegistry,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
    TaskRunExecutorResult,
)
from runtime.v3_handlers import get_v3_handlers


class V3Runtime:
    """
    Production composition root for Task V3.

    This class assembles the existing V3 runtime components and
    exposes a stable execution entrypoint.
    """

    def __init__(
        self,
        goal_registry: GoalRegistry,
        target_directory: TargetDirectory,
        handler_registry: HandlerRegistry,
        precondition_registry: PreconditionRegistry | None = None,
        assertion_registry: AssertionRegistry | None = None,
    ) -> None:
        self.goal_registry = goal_registry
        self.target_directory = target_directory
        self.handler_registry = handler_registry

        self.precondition_registry = (
            precondition_registry
            if precondition_registry is not None
            else PreconditionRegistry()
        )

        self.assertion_registry = (
            assertion_registry
            if assertion_registry is not None
            else AssertionRegistry()
        )

        self.precondition_evaluator = (
            PreconditionEvaluator(
                self.precondition_registry
            )
        )

        self.executor = TaskRunExecutor(
            goal_registry=self.goal_registry,
            target_directory=self.target_directory,
            handler_registry=self.handler_registry,
            precondition_evaluator=self.precondition_evaluator,
            assertion_registry=self.assertion_registry,
        )
    @classmethod
    def create_default(cls) -> V3Runtime:
        goal_registry = GoalRegistry()
        handler_registry = HandlerRegistry()
        target_directory = TargetDirectory()

        from runtime.v3_registry import register_v3_defaults
        from runtime.v3_targets import register_v3_targets

        register_v3_defaults(
            goal_registry,
            handler_registry,
        )

        register_v3_targets(
            target_directory,
        )

        return cls(
            goal_registry=goal_registry,
            target_directory=target_directory,
            handler_registry=handler_registry,
        )
    def execute(
        self,
        task: TaskV3,
        handler_context: HandlerRuntimeContext | None = None,
        goal_preconditions: tuple[Precondition, ...] = (),
        runtime_safety_preconditions: tuple[Precondition, ...] = (),
        cancellation_token: CancellationToken | None = None,
        transaction_policy=None,
    ) -> TaskRunExecutorResult:
        """
        Execute one TaskV3 using the production V3 handler set.
        """

        return self.executor.execute(
            task,
            handlers=get_v3_handlers(),
            handler_context=handler_context,
            goal_preconditions=goal_preconditions,
            runtime_safety_preconditions=runtime_safety_preconditions,
            cancellation_token=cancellation_token,
            transaction_policy=transaction_policy,
        )
