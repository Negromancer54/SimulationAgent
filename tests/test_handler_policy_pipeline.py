from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TargetKind,
    TaskV3,
)

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)

from registries.handler_registry import (
    HandlerApplicability,
    HandlerExecutionPolicy,
    HandlerRegistry,
    HandlerSpec,
)

from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)

from runtime.assertions import (
    AssertionRegistry,
)

from runtime.execution_policy import (
    ResourcePolicy,
    RuntimeExecutionLimits,
)

from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)

from runtime.task_run import (
    TaskRunStatus,
)

from runtime.task_run_executor import (
    TaskRunExecutor,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task() -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp",
        ),
    )

    goal = TaskGoal(
        identifier=GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=GOAL_VERSION,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id="handler-policy-pipeline-test",
        description="Verify handler policy integration.",
        intent=intent,
    )


def make_target_directory() -> TargetDirectory:
    directory = TargetDirectory()

    directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    return directory


def make_handler_registry(
    execution_policy: HandlerExecutionPolicy | None = None,
) -> HandlerRegistry:
    registry = HandlerRegistry()

    registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,),
            ),
            execution_policy=execution_policy,
        )
    )

    return registry


def make_executor(
    handler_execution_policy: HandlerExecutionPolicy | None = None,
    runtime_limits: RuntimeExecutionLimits | None = None,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Add the generic component API.",
            owner="PROJECT",
        )
    )

    precondition_registry = PreconditionRegistry()
    precondition_evaluator = PreconditionEvaluator(
        precondition_registry
    )

    assertion_registry = AssertionRegistry()

    return TaskRunExecutor(
        goal_registry,
        make_target_directory(),
        make_handler_registry(handler_execution_policy),
        precondition_evaluator,
        assertion_registry,
        runtime_execution_limits=runtime_limits,
    )


def test_selected_handler_policy_reaches_task_run() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=60,
        max_attempts=7,
        max_workers=8,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=120,
        max_attempts=10,
        max_workers=12,
    )

    executor = make_executor(
        handler_execution_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 60
    assert policy.max_attempts == 7
    assert policy.max_workers == 8


def test_handler_policy_is_intersected_with_runtime_limits() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=120,
        max_attempts=10,
        max_workers=8,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=90,
        max_attempts=4,
        max_workers=6,
    )

    executor = make_executor(
        handler_execution_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 90
    assert policy.max_attempts == 4
    assert policy.max_workers == 6


def test_handler_policy_cannot_expand_runtime_limits() -> None:
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=300,
        max_attempts=20,
        max_workers=16,
    )

    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=45,
        max_attempts=3,
        max_workers=2,
    )

    executor = make_executor(
        handler_execution_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 45
    assert policy.max_attempts == 3
    assert policy.max_workers == 2


def test_handler_without_policy_preserves_runtime_limits() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=75,
        max_attempts=5,
        max_workers=4,
    )

    executor = make_executor(
        handler_execution_policy=None,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 75
    assert policy.max_attempts == 5
    assert policy.max_workers == 4


def test_handler_and_runtime_resource_policies_are_intersected() -> None:
    handler_policy = HandlerExecutionPolicy(
        resources=ResourcePolicy(
            values={
                "cpu": 8,
                "memory": 16,
            }
        )
    )

    runtime_limits = RuntimeExecutionLimits(
        resources=ResourcePolicy(
            values={
                "cpu": 4,
                "memory": 32,
            }
        )
    )

    executor = make_executor(
        handler_execution_policy=handler_policy,
        runtime_limits=runtime_limits,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result.completed

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.resources.values == {
        "cpu": 4,
        "memory": 16,
    }
