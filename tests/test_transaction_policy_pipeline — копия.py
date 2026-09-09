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

from runtime.assertions import AssertionRegistry

from runtime.execution_policy import (
    FailureMode,
    ResourcePolicy,
    RuntimeExecutionLimits,
    TransactionExecutionPolicy,
)

from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)

from runtime.task_run import TaskRunStatus

from runtime.task_run_executor import TaskRunExecutor


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
        task_id="transaction-policy-pipeline-test",
        description="Verify transaction policy integration.",
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
    failure_mode: FailureMode | None = None,
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
            execution_policy=HandlerExecutionPolicy(
                timeout_seconds=120,
                max_attempts=10,
                max_workers=8,
                resources=ResourcePolicy(
                    values={
                        "cpu": 8,
                        "memory": 16,
                    }
                ),
                failure_mode=failure_mode,
            ),
        )
    )

    return registry


def make_executor(
    runtime_limits: RuntimeExecutionLimits,
    handler_failure_mode: FailureMode | None = None,
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

    return TaskRunExecutor(
        goal_registry,
        make_target_directory(),
        make_handler_registry(handler_failure_mode),
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        runtime_execution_limits=runtime_limits,
    )


def test_transaction_policy_limits_reach_effective_policy() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=180,
        max_attempts=12,
        max_workers=10,
        resources=ResourcePolicy(
            values={
                "cpu": 16,
                "memory": 32,
            }
        ),
    )

    executor = make_executor(runtime_limits)

    transaction_policy = TransactionExecutionPolicy(
        timeout_seconds=30,
        max_attempts=3,
        max_workers=4,
        resources=ResourcePolicy(
            values={
                "cpu": 4,
                "memory": 8,
            }
        ),
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        transaction_policy=transaction_policy,
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 30
    assert policy.max_attempts == 3
    assert policy.max_workers == 4
    assert policy.resources.values == {
        "cpu": 4,
        "memory": 8,
    }


def test_transaction_policy_cannot_expand_handler_or_runtime_limits() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=60,
        max_attempts=5,
        max_workers=4,
        resources=ResourcePolicy(
            values={
                "cpu": 4,
                "memory": 16,
            }
        ),
    )

    executor = make_executor(runtime_limits)

    transaction_policy = TransactionExecutionPolicy(
        timeout_seconds=300,
        max_attempts=50,
        max_workers=32,
        resources=ResourcePolicy(
            values={
                "cpu": 32,
                "memory": 64,
            }
        ),
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        transaction_policy=transaction_policy,
    )

    assert result.completed

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.timeout_seconds == 60
    assert policy.max_attempts == 5
    assert policy.max_workers == 4
    assert policy.resources.values == {
        "cpu": 4,
        "memory": 16,
    }


def test_no_transaction_policy_preserves_existing_handler_pipeline() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=90,
        max_attempts=6,
        max_workers=5,
    )

    executor = make_executor(runtime_limits)

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
    assert policy.max_attempts == 6
    assert policy.max_workers == 5


def test_transaction_only_failure_mode_is_allowed_when_handler_has_none() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=90,
        max_attempts=6,
        max_workers=5,
    )

    executor = make_executor(runtime_limits)

    transaction_policy = TransactionExecutionPolicy(
        failure_mode=FailureMode.CONTINUE,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        transaction_policy=transaction_policy,
    )

    assert result.completed
    assert result.run.status is TaskRunStatus.COMPLETED

    policy = result.run.effective_execution_policy

    assert policy is not None
    assert policy.failure_mode is FailureMode.CONTINUE


def test_transaction_and_handler_conflicting_failure_modes_reject_policy() -> None:
    runtime_limits = RuntimeExecutionLimits(
        timeout_seconds=90,
        max_attempts=6,
        max_workers=5,
    )

    executor = make_executor(
        runtime_limits,
        handler_failure_mode=FailureMode.ABORT,
    )

    transaction_policy = TransactionExecutionPolicy(
        failure_mode=FailureMode.CONTINUE,
    )

    result = executor.execute(
        make_task(),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        transaction_policy=transaction_policy,
    )

    assert not result.completed
    assert result.run.status is TaskRunStatus.FAILED
    assert result.run.execution is None
    assert result.run.effective_execution_policy is None
